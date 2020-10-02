#!/usr/bin/python3

# SPDX-FileCopyrightText: 2020 Nicolás Alvarez <nicolas.alvarez@gmail.com>
#
# SPDX-License-Identifier: MIT

import sys
import datetime
import re
import requests
from bs4 import BeautifulSoup
import icalendar

session = requests.session()
session.headers.update({'User-Agent': 'NerdearlaICS/0.1 (+nicolas.alvarez@gmail.com)'})

from dataclasses import dataclass

@dataclass
class Talk:
    uid: str = None
    title: str = None
    container: str = None
    day: datetime.date = None
    time_start: datetime.time = None
    time_end: datetime.time = None
    description: str = None

DAYS = [datetime.date(2020, 10, d) for d in (20,21,22,23,24)]

def get_talks():
    r = session.get("https://nerdear.la/agenda")
    if r.status_code == 200:
        html_doc = r.text
        soup = BeautifulSoup(html_doc, 'html.parser')

        day_elems = soup.find_all('ul', class_='scheduleday_wrapper')
        for day_elem in day_elems:

            day_title_elem = day_elem.find('li', class_='scheduleday_title').find('div', class_='scheduleday_title_content')
            day_title = next(day_title_elem.stripped_strings)
            m = re.match('Día (\d+) . Container ([ABC])', day_title)
            day_num = int(m.group(1))
            container = m.group(2)

            talk_elems = day_elem.find_all('div', class_='session_content_wrapper')
            for talk_elem in talk_elems:
                title_elem = talk_elem.find('div', class_='session_title_cl')
                assert title_elem
                link_elem = title_elem.find('a')

                talk = get_talk(link_elem['href'])
                if not talk.day:
                    talk.day = DAYS[day_num-1]
                if not talk.container:
                    talk.container = container

                print(talk.uid, file=sys.stderr)
                yield talk

def get_talk(url):
    r = session.get(url)
    if r.status_code == 200:
        html_doc = r.text
        soup = BeautifulSoup(html_doc, 'html.parser')
        talk = Talk()

        talk.uid = re.match('.*/session/([^/]+)/?$', url).group(1)

        title_elems = soup.select('div#page_caption div.page_title_content h3')
        if len(title_elems) == 1:
            talk.title = title_elems[0].string

        tagline_elems = soup.select('div#page_caption div.page_title_content div.page_tagline')
        if len(tagline_elems) == 1:
            tagline_parts = list(tagline_elems[0].stripped_strings)
            tagline_info = None
            if   len(tagline_parts) == 1: tagline_time, = tagline_parts
            elif len(tagline_parts) == 2: tagline_info, tagline_time = tagline_parts
            
            m = re.match('(\d\d):(\d\d) [-–](?: (\d\d):(\d\d))?', tagline_time)
            if m:
                talk.time_start = datetime.time(int(m.group(1)), int(m.group(2)))
                if m.group(4):
                    talk.time_end = datetime.time(int(m.group(3)), int(m.group(4)))

        content_elems = soup.select('div#page_content_wrapper div.post_content_wrapper p')
        content_paragraphs = []
        for pelem in content_elems:
            content_paragraphs.append('\n'.join(pelem.stripped_strings))
        talk.description = '\n\n'.join(content_paragraphs)

        return talk

ART = datetime.timezone(-datetime.timedelta(hours=3))

def make_vevent(talk):
    event = icalendar.Event()
    event.add('uid', talk.uid + talk.container + '-2020@nerdear.la')
    event.add('dtstamp', datetime.datetime.utcnow())
    event.add('dtstart', datetime.datetime.combine(talk.day, talk.time_start, ART))
    if talk.time_end:
        event.add('dtend', datetime.datetime.combine(talk.day, talk.time_end, ART))

    event.add('location', f'Container {talk.container}')
    event.add('summary', talk.title)
    if talk.description != '':
        event.add('description', talk.description)

    return event

def make_ical(talks):
    cal = icalendar.Calendar()
    for talk in talks:
        event = make_vevent(talk)
        cal.add_component(event)

    return cal

def filter_duplicates(talks):
    talk_ids_seen = set()
    for talk in talks:
        if talk.uid in talk_ids_seen: continue
        if talk.uid.startswith('comienzo-'): continue
        if 'to-be-announc' in talk.uid: continue
        
        talk_ids_seen.add(talk.uid)
        yield talk

ical = make_ical(filter_duplicates(get_talks()))

sys.stdout.write(ical.to_ical().decode('utf8'))

