import re
import time
import json
from typing import List, Dict

import requests
from datetime import datetime, date



# Paste your discourse cookies below
_t = "abcd" 
_forum_session = "abcd"


class DiscourseScraper:

    def __init__(self, category_id: int):
        self.base_url = "https://discourse.onlinedegree.iitm.ac.in"
        self.category_id = category_id
        self.session = self._create_session()


    def scrape_forum(self, start_date_str: str, end_date_str: str) -> List[Dict]:
        # Convert date strings to datetime objects for comparison
        start_date = self._date(start_date_str)
        end_date = self._date(end_date_str)
    
        all_posts = list()
        page_index = 0
        
        while True:
            # Get the latest topics for the current page
            topics = self._get_latest_topics(page_index)
            if not topics:
                break  # No more topics to process
            
            first_topic_date = self._date(topics[0]['last_posted_at'][:10])
            if first_topic_date < start_date:
                break  # All older threads are before start date

            for topic in topics:
                # Check if topic has any activity in our date range
                topic_last_posted = self._date(topic['last_posted_at'][:10])
                topic_created = self._date(topic['created_at'][:10])
                
                # Skip topic if it's entirely outside our date range
                if (topic_last_posted < start_date) or (topic_created > end_date):
                    continue
                
                # Get all posts from this topic that fall within our date range
                topic_posts = self._scrape_topic_posts(topic, start_date, end_date)
                print(f'scrapped {len(topic_posts)} posts under topic {topic['id']}')
                all_posts.extend(topic_posts)
            
            page_index += 1
            time.sleep(0.1)  

        with open('data/json/posts.json', 'w') as file:
            json.dump(all_posts, file, indent=4)
            
        return all_posts
    
    
    def _create_session(self):
        domain = "discourse.onlinedegree.iitm.ac.in"
        session = requests.Session()
        cookies = dict(_t = _t, _forum_session = _forum_session)

        for name, value in cookies.items():
            session.cookies.set(name, value, domain=domain)

        session.headers.update({'Accept': 'application/json'})
        return session



    def _get_latest_topics(self, page_index: int) -> List[Dict]:
        url = f"{self.base_url}/c/{self.category_id}.json?page={page_index}"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()['topic_list']['topics']
        except (requests.RequestException, ValueError) as e:
            print(f"Error fetching latest topics page {page_index}: {e}")
            return []
        
    
    def _scrape_topic_posts(self, topic: Dict, start_date: date, end_date: date) -> List[Dict]:
        topic_posts = list()
        page_index = 1
        
        while True:
            # Get posts for the current page of the topic
            posts = self._get_topic_posts(topic['id'], page_index)
            if not posts:
                break
                
            for post in posts:
                post_created = self._date(post['created_at'][:10])
                post_updated = self._date(post['updated_at'][:10])
                
                # Check if post was created or updated within our date range
                if (start_date <= post_created <= end_date) or (start_date <= post_updated <= end_date):
                    topic_posts.append(self._extract_post_info(post))
            
            # Optimization: If we've passed the date range, we can stop
            oldest_post_date = min(self._date(post['created_at'][:10]) for post in posts)
            if oldest_post_date < start_date:
                break
                
            page_index += 1
            time.sleep(0.1)  
        return topic_posts
    

    def _get_topic_posts(self, topic_id: str, page_index: int) -> List[Dict]:
        url = f"{self.base_url}/t/{topic_id}.json?include_raw=true&page={page_index}"
        response = self.session.get(url)
        if response.status_code == 200:
            return response.json()['post_stream']['posts']
        elif response.status_code == 404:
            return []
        else:
            raise Exception(response.json())

    def _extract_post_info(self, post: Dict) -> Dict:
        post_info = dict(
            post_url = self.base_url + post['post_url'],
            topic_title = post['topic_slug'].replace('-', ' '),
            markdown = self._clean_markdown(post['raw']),
            user_title = post['user_title'],
            post_number = post['post_number'],
            reply_count = post['reply_count'],
            reply_to_post_number = post['reply_to_post_number'],
            accepted_answer = post['accepted_answer'],
            image_urls = self._extract_image_urls(post['cooked'])
        )
        return post_info

    def _extract_image_urls(self, html: str) -> List[str]:
        exts = ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp']
        href_regex = re.compile(r'href=(["\'])(.*?)\1', re.IGNORECASE)
        ext_pattern = '|'.join(re.escape(ext) for ext in exts)
        image_regex = re.compile(rf'\.({ext_pattern})(?:[?#].*)?$', re.IGNORECASE)
        results = []
        for match in href_regex.finditer(html):
            url = match.group(2)
            # Must start with https://
            if not url.lower().startswith('https://'):
                continue
            # Must end in a valid image extension
            if not image_regex.search(url):
                continue
            results.append(url)
        return results

    def _clean_markdown(self, markdown_text: str) -> str:
        # remove image upload links from markdown
        new_text = re.sub(r'\[\!.*?\]\(.*?\)', '', markdown_text)
        new_text = re.sub(r'!\[.*?\]\(upload://.*?\)', '', new_text)
        return new_text
    
    def _date(self, date: str)-> date:
        return datetime.strptime(date, '%Y-%m-%d').date()



