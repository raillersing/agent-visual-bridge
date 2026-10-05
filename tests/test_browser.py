"""Real Chromium journeys; install the qualification extra and Chromium to run."""
import json

import pytest

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import sync_playwright, expect

from agent_visual_bridge import ReviewService, CooperativeAgent
from agent_visual_bridge.api import LocalServer
from agent_visual_bridge.core import VisualBridge
from agent_visual_bridge.parser import parse_html_file


@pytest.fixture
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


def test_english_browser_review_preserves_submitted_constraints(browser, tmp_path):
    service = ReviewService(tmp_path / 'english.db')
    service.settings('english-project', {'preferences': {'language': 'en'}})
    review = service.create_review({'project_id': 'english-project', 'items': [{'id': 'a', 'title': 'API scope'}]})
    with LocalServer(service, review['review_id']) as server:
        page = browser.new_page()
        page.goto(server.url)
        expect(page.locator('#summary')).to_contain_text('pending item(s)')
        page.locator('#status-a').select_option('approve')
        page.locator('#constraints-a').fill('Preserve the public API')
        page.locator('#submit').click()
        expect(page.locator('#mandate-text')).to_contain_text('Pending items remain unauthorized')
        page.locator('#confirm').click()
        expect(page.locator('#notice')).to_contain_text('Decisions saved. Receipt')
        stored = ReviewService(service.store.path).get_review(review['review_id'])
        assert stored['decisions']['a']['constraints'] == ['Preserve the public API']


def test_browser_partial_decision_reload_question_revision_and_control(browser, tmp_path):
    service = ReviewService(tmp_path/'reviews.db')
    review = service.create_review({'title':'Human review', 'report_type':'plan', 'items':[
        {'id':'a','title':'API contract','scope':'src/', 'recommendation':'Keep compatibility',
         'diff':'-old\n+new','evidence':[{'kind':'tool_result','source':'contract test','content':'passed'}]},
        {'id':'b','title':'Database choice','interaction_kind':'clarify','options':['Postgres','SQLite']} ]})
    agent = CooperativeAgent(service, review['review_id'], lambda item, constraints: [{'source':'executor','content':constraints}])
    with LocalServer(service, review['review_id']) as server:
        page=browser.new_page(viewport={'width':360,'height':800})
        errors=[]
        page.on('pageerror',lambda error: errors.append(str(error)))
        page.goto(server.url)
        page.locator('#status-a').select_option('approve')
        page.locator('#remark-a').fill('Only src/, keep compatibility')
        page.locator('#constraints-a').fill('No database migration')
        page.locator('#submit').click()
        assert 'Only src/' in page.locator('#mandate-text').inner_text()
        page.locator('#confirm').click()
        expect(page.locator('#notice')).to_contain_text('Reçu')
        state=ReviewService(service.store.path).get_review(review['review_id'])
        assert state['state']=='partially_submitted'
        assert state['decisions']['a']['constraints']==['No database migration']
        page.reload()
        assert page.locator('#remark-a').input_value()=='Only src/, keep compatibility'
        page.locator('article[data-id="b"] .conversation summary').click()
        page.locator('#question-b').fill('Why Postgres?')
        page.locator('article[data-id="b"] .ask').click()
        expect(page.locator('#notice')).to_contain_text('Question enregistrée')
        service.publish_item_reply(review['review_id'],'b','Transactional integrity',category='fact')
        expect(page.locator('article[data-id="b"] .thread')).to_contain_text('Transactional integrity')
        page.locator('[data-control="pause"]').click()
        assert agent.run_next()['state']=='paused'
        expect(page.locator('#control-status')).to_contain_text('applied')
        page.locator('article[data-id="a"] summary').filter(has_text='Ajuster').click()
        page.locator('#scope-a').fill('src/contracts/')
        page.locator('article[data-id="a"] .revise').click()
        expect(page.locator('#notice')).to_contain_text('Nouvelle')
        assert service.get_review(review['review_id'])['revision']==2
        assert 'a' not in service.get_review(review['review_id'])['decisions']
        page.reload()
        assert page.locator('#status-a').input_value()=='pending'
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.evaluate("document.body.style.fontSize='140%'")
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors
        page.close()


def test_offline_explicit_export_and_safe_saved_html(browser,tmp_path):
    bridge=VisualBridge.from_data({'title':'Offline','items':[{'id':'a','title':'Task'}]})
    path=bridge.save_html(tmp_path/'report.html')
    page=browser.new_page(accept_downloads=True)
    page.goto(path.as_uri())
    page.locator('#status-a').select_option('approve')
    message='Keep &lt; literal and </script><script>window.evil=true</script>'
    page.locator('#remark-a').fill(message)
    page.locator('#submit').click()
    with page.expect_download() as download:
        page.locator('#confirm').click()
    exported=tmp_path/'decisions.json'
    download.value.save_as(exported)
    feedback=json.loads(exported.read_text())
    assert feedback['decisions'][0]['comment']==message
    with page.expect_download() as download:
        page.locator('#save').click()
    saved=tmp_path/'saved.html'
    download.value.save_as(saved)
    assert 'const AVB_RUNTIME = {"preferences":{}};' in saved.read_text()
    assert parse_html_file(saved)['decisions'][0]['comment']==message
    page.goto(saved.as_uri())
    assert page.evaluate('window.evil') is None
    assert page.locator('#remark-a').input_value()==message
    page.close()


@pytest.mark.parametrize('kind,field,value',[('audit','verdict','non-conforme'),
    ('plan','lot','Lot Alpha'),('review','diff','+new_line'),('decision','options',['Option Alpha'])])
def test_four_views_render_real_data(browser,tmp_path,kind,field,value):
    data={'title':'Report','report_type':kind,'items':[{'id':'a',field:value}]}
    page=browser.new_page()
    page.goto(VisualBridge.from_data(data).save_html(tmp_path/f'{kind}.html').as_uri())
    page.locator('article details summary').first.click()
    assert ('Option Alpha' if kind=='decision' else value) in page.locator('article').inner_text()
    page.close()


def test_native_mcp_apps_bridge_in_chromium(browser,tmp_path):
    from pathlib import Path
    from agent_visual_bridge.templates import render_review, render_app_resource
    host=Path(__file__).parent.parent/'ui/out/test-host.js'
    if not host.exists():
        pytest.skip('Run npm ci --prefix ui and npm run --prefix ui build:host')
    service=ReviewService(tmp_path/'native.db')
    review=service.create_review({'title':'Native review','items':[{'id':'a'}]})
    with LocalServer(service,review['review_id']) as server:
        page=browser.new_page()
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.route(server.url,lambda route:route.fulfill(body='<html><body></body></html>',content_type='text/html'))
        page.goto(server.url)
        page.add_script_tag(content=host.read_text())
        page.evaluate('(config)=>window.startAvbHost(config)',{'token':server.human_token,'review':review,
            'html':render_review(review,{'app':True}),'resource':render_app_resource()})
        frame=page.frame_locator('iframe')
        expect(frame.locator('#status-a')).to_be_visible(timeout=10000)
        frame.locator('#status-a').select_option('approve')
        frame.locator('#remark-a').fill('Native constraint')
        frame.locator('#submit').click()
        frame.locator('#confirm').click()
        expect(frame.locator('#notice')).to_contain_text('Reçu',timeout=10000)
        stored=ReviewService(service.store.path).get_review(review['review_id'])
        assert stored['decisions']['a']['comment']=='Native constraint'
        assert 'enregistrées' in page.evaluate('window.humanMessage.content[0].text')
        assert not errors
        page.close()


def test_keyboard_narrow_layout_enlarged_text_and_submission_lock(browser, tmp_path):
    service = ReviewService(tmp_path/'accessible.db')
    review = service.create_review({'title':'Long plan title for accessible reading','items':[
        {'id':'a','title':'Preserve public API','description':'Readable context '*20}]})
    with LocalServer(service, review['review_id']) as server:
        page = browser.new_page(viewport={'width':320,'height':900})
        page.goto(server.url)
        page.add_style_tag(content='html {font-size: 24px}')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('#status-a').focus()
        page.keyboard.press('ArrowDown')
        page.keyboard.press('Tab')
        assert page.locator('#status-a').input_value() == 'approve'
        page.locator('#remark-a').fill('Keep compatibility')
        page.locator('#submit').focus()
        page.keyboard.press('Enter')
        expect(page.locator('#mandate')).to_be_visible()
        page.locator('#confirm').focus()
        page.keyboard.press('Enter')
        expect(page.locator('#notice')).to_contain_text('Reçu')
        expect(page.locator('#status-a')).to_be_disabled()
        assert service.get_review(review['review_id'])['decisions']['a']['comment'] == 'Keep compatibility'
        page.screenshot(path='/tmp/avb-mobile-qualification.png', full_page=True)
