import os
import re
import json
import datetime
import dateutil.parser
import urllib.request


def get_new_posts(delta):
    assert type(delta) == datetime.timedelta
    url = 'https://api.github.com/graphql'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'bearer {}'.format(os.environ.get('GITHUB_API_TOKEN')),
    }
    with open('fetch.graphql') as f:
        data = { 'query': f.read() }
    req = urllib.request.Request(url, json.dumps(data).encode(), headers)
    with urllib.request.urlopen(req) as res:
        data = json.load(res)
    since = datetime.datetime.now(datetime.timezone.utc) - delta
    posts = []
    for post in data['data']['repository']['issues']['edges']:
        post = post['node']
        post['createdAt'] = dateutil.parser.parse(post['createdAt'])
        if post['createdAt'] < since:
            continue
        matched = re.match(r'^## 一言でいうと\r\n(.+?)\r\n###', post['body'], flags=re.DOTALL)
        if not matched:
            continue
        post['headline'] = matched[1]
        matched = re.match(r'^(.+)!\[.*?\]\((.+?)\)\s*$', post['headline'], flags=re.DOTALL)
        if matched:
            post['headline'] = matched[1]
            post['imageUrl'] = matched[2]
        else:
            post['imageUrl'] = None
        post['labels'] = [label['node']['name'] for label in post['labels']['edges']]
        posts.append(post)
    return posts


def to_slack_attachment(post):
    attachment = {
        'title': post['title'],
        'title_link': post['url'],
        'text': post['headline'],
        'mrkdwn_in': ['text'],
        'image_url': post['imageUrl'],
        'footer': post['author']['login'],
        'footer_icon': post['author']['avatarUrl'],
        'ts': int(post['createdAt'].timestamp()),
    }
    if len(post['labels']) > 0:
        labels = ' '.join(['`{}`'.format(label) for label in post['labels']])
        attachment['text'] = labels + '\n' + attachment['text']
    return attachment


def handler(event, context):
    posts = get_new_posts(datetime.timedelta(hours=1))
    if len(posts) == 0:
        return
    url = os.environ.get('SLACK_INCOMING_WEBHOOK_URL')
    data = { 'attachments': [to_slack_attachment(post) for post in posts] }
    data = json.dumps(data).encode()
    req = urllib.request.Request(url, data)
    urllib.request.urlopen(req)
