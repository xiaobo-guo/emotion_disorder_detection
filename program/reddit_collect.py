import praw
import json
import re
import requests
import os
import argparse
import time
from multiprocessing import Pool

reddit_isntance_args = {"client_id": "qOCFmW7rYl8P2A", "client_secret": "-RxOwpvQts9Y7lxmkFk-p9lleZc",
                        "password": "19960906", "user_agent": "testscript by /u/bipolar",
                        "username": "gxb_96"}

bipolar_subreddit_list = ["bipolar", "bipolar2",
                          "BipolarReddit", "BipolarSOs", "bipolarart", "mentalhealth"]
depression_subreddit_list = ["depression", "mentalhealth"]
anxiety_subreddit_list = ["Anxiety", "mentalhealth","Anxietyhelp","socialanxiety"]
data_type_list = ['bipolar', 'depression', 'background']

begin_utc_time = 1451624400
end_utc_time = 1592280000
# end_utc_time is 2020.6.16
# begin_utc_time is 2016.1.1 changed from 2018.1.1
user_from_reddit = False
comment_from_reddit = False


class GetFromReddit(object):
    def __init__(self, client_id, client_secret, password, user_agent, username):
        super().__init__()
        self._reddit_instance = praw.Reddit(client_id=client_id, client_secret=client_secret,
                                            password=password, user_agent=user_agent,
                                            username=username)
        self.comments = None


class GetCommentsFromReddit(GetFromReddit):
    def __init__(self, client_id, client_secret, password, user_agent, username, subreddit_name):
        super().__init__(client_id, client_secret, password, user_agent, username)
        self._subreddit_name = subreddit_name
        self._subreddit = self._reddit_instance.subreddit(self._subreddit_name)

    def get_comments(self, comment_number, type='comment'):
        if type == 'comment':
            self.comments = self._subreddit.comments(limit=comment_number)
        elif type == 'hot':
            self.comments = self._subreddit.hot(limit=comment_number)
        comment_list = []
        for comment in self.comments:
            comment_list.append(comment)
        return comment_list


class GetUserCommentsFromReddit(GetFromReddit):
    def __init__(self, client_id, client_secret, password, user_agent, username, reddit_username):
        super().__init__(client_id, client_secret, password, user_agent, username)
        self._reddit_username = reddit_username
        self._user = self._reddit_instance.redditor(self._reddit_username)
        self._comment_list = list()

    def get_comments(self, comment_number=1000, subreddit_list=[]):
        for comment in self._user.comments.new(limit=comment_number):
            comment_id = comment.id
            text = comment.body.replace('\n', '')
            subreddit_info = re.compile(r'r/[^ ]+')
            text = re.sub(subreddit_info, '', text)
            link_id = comment.link_id
            time = comment.created_utc
            if not subreddit_list:
                self._comment_list.append(
                    {comment_id: {'text': text, 'link_id': link_id, 'time': time}})
            else:
                if comment.subreddit.display_name in subreddit_list:
                    self._comment_list.append(
                        {comment_id: {'text': text, 'link_id': link_id, 'time': time}})
        return self._comment_list


class GetCommentsFromPushshift(object):
    def __init__(self, query, subreddit, start_time):
        super().__init__()
        self._query = query
        self.comments = None
        self._subreddit = subreddit
        self._url = None
        self.build_URL(start_time)

    def build_URL(self, utc_time):
        self._url = 'https://api.pushshift.io/reddit/search/comment/?search=' + \
            self._query + '&size=500&before=' + str(utc_time) + \
            '&subreddit=' + self._subreddit

    def get_comments(self):
        data = requests.get(self._url)
        self.comments = json.loads(data.text)['data']
        utc_time = self.comments[-1]['created_utc']
        return self.comments, utc_time


class GetUserCommentsFromPushshift(object):
    def __init__(self, author, end_time):
        super().__init__()
        self._comment_list = []
        self._author = author
        self._url = None
        self._end_time = end_time

    def build_URL(self, utc_time):
        self._url = 'https://api.pushshift.io/reddit/search/comment/?size=500&before=' + str(utc_time) + \
            '&author=' + self._author

    def get_comments(self, subreddit_list=[]):
        while self._end_time > begin_utc_time:
            self.build_URL(self._end_time)
            data = requests.get(self._url)
            while data.status_code == 429:
                time.sleep(1)
                data = requests.get(self._url)
            data = json.loads(data.text)['data']
            if data == []:
                break
            for item in data:
                comment_id = item['id']
                text = item['body'].replace('\n', '')
                subreddit_info = re.compile(r'r/[^ ]+')
                text = re.sub(subreddit_info, '', text)
                link_id = item['link_id']
                post_time = item['created_utc']
                flair_text  = item['author_flair_text']
                if not subreddit_list:
                    self._comment_list.append(
                        {comment_id: {'text': text, 'link_id': link_id, 'time': post_time,'author_flair':flair_text}})
                else:
                    if item['subreddit'] in subreddit_list:
                        self._comment_list.append(
                            {comment_id: {'text': text, 'link_id': link_id, 'time': post_time,'author_flair':flair_text}})
            self._end_time = post_time
        return self._comment_list


def get_bipolar_data():
    user_list = _get_check_user_list(data_type_list)
    get_comments(user_list, bipolar_subreddit_list, 'bipolar',
                 begin_utc_time=begin_utc_time, end_utc_time=end_utc_time)


def get_depression_data():
    user_list = _get_check_user_list(data_type_list)
    get_comments(user_list, depression_subreddit_list, 'depression',
                 begin_utc_time=begin_utc_time, end_utc_time=end_utc_time)


def get_anxiety_data():
    user_list = _get_check_user_list(data_type_list)
    get_comments(user_list, anxiety_subreddit_list, 'anxiety',
                 begin_utc_time=begin_utc_time, end_utc_time=end_utc_time)

def get_background_data():
    user_list = _get_check_user_list(data_type_list)
    get_comments(user_list, ['all'], 'background', data_type='hot',
                 begin_utc_time=begin_utc_time, end_utc_time=end_utc_time)


def get_comments(checked_user_list, subreddit_list, key_words, data_type='comment', begin_utc_time=None, end_utc_time=None):
    utc_time = end_utc_time
    while utc_time > begin_utc_time:
        user_list = set()
        for subreddit_name in subreddit_list:
            if user_from_reddit:
                utc_time = begin_utc_time
                get_reddit_comments = GetCommentsFromReddit(
                    **reddit_isntance_args, subreddit_name=subreddit_name)
                comments_list = get_reddit_comments.get_comments(
                    1000, type=data_type)
                for comment in comments_list:
                    if comment.author is not None and comment.author.name not in checked_user_list:
                        user_list.add(comment.author.name)
                        checked_user_list.add(comment.author.name)
            else:
                try:
                    get_pushshift_comments = GetCommentsFromPushshift(
                        key_words, subreddit_name, utc_time)
                    comments_list, utc_time = get_pushshift_comments.get_comments()
                    for comment in comments_list:
                        if comment['author'] is not None and comment['author'] not in checked_user_list:
                            user_list.add(comment['author'])
                            checked_user_list.add(comment['author'])
                except:
                    continue
        error_count = 0
        for index, user in enumerate(user_list):
            try:
                if comment_from_reddit:
                    get_user_comments = GetUserCommentsFromReddit(
                        **reddit_isntance_args, reddit_username=user)
                    comment_list = get_user_comments.get_comments(
                        comment_number=1000)
                else:
                    get_user_comments = GetUserCommentsFromPushshift(
                        user, end_utc_time)
                    comment_list = get_user_comments.get_comments()
                if key_words == 'bipolar':
                    check_function = _identify_bipolar
                elif key_words == 'depression':
                    check_function = _identify_depression
                elif key_words == 'anxiety':
                    check_function = _identify_anxiety
                elif key_words == 'background':
                    check_function = _identify_background
                if check_function(user, comment_list):
                    checked_user_list.add(user)
                    with open('data/reddit/'+key_words+'/'+user, mode='w', encoding='utf8') as fp:
                        for comment in comment_list:
                            comment = json.dumps(comment)
                            fp.write(comment + '\n')
                time.sleep(1)
            except:
                error_count += 1
                continue
        print(error_count)
        print(utc_time)


def _identify_bipolar(username, comment_list):
    identify_list = ["I am diagnosed with bipolar", "i am diagnosed with bipolar",
                     "I'm diagnosed with bipolar", "i'm diagnosed with bipolar", "I have been diagnosed with bipolar",
                     "I was diagnosed with bipolar", "I've been diagnosed with bipolar", "I was just diagnosed with bipolar",
                     "I was diagnosed with depression and anxiety", "I've been diagnosed with depression and anxiety",
                     "I am diagnosed with depression and anxiety", ]

    for comment in comment_list:
        for key, value in comment.items():
            text = value['text']
            for sentence in identify_list:
                if sentence in text:
                    with open('data/user_list/bipolar_user_list', mode='a', encoding='utf8') as file:
                        file.write(username+' [info] '+text+'\n')
                    return True
    return False

def _identify_depression(username, comment_list):
    identify_list = ["I am diagnosed with depression", "i am diagnosed with depression",
                     "I'm diagnosed with depression", "i'm diagnosed with depression", "I have been diagnosed with depression",
                     "I was diagnosed with depression", "I've been diagnosed with depression", "I was just diagnosed with depression"]

    for comment in comment_list:
        for key, value in comment.items():
            text = value['text']
            for sentence in identify_list:
                if sentence in text and 'anxiety' not in text:
                    with open('data/user_list/depression_user_list', mode='a', encoding='utf8') as file:
                        file.write(username+' [info] '+text+'\n')
                    return True
    return False

def _identify_anxiety(username, comment_list):
    identify_list = ["I am diagnosed with anxiety", "i am diagnosed with anxiety",
                     "I'm diagnosed with anxiety", "i'm diagnosed with anxiety", "I have been diagnosed with anxiety",
                     "I was diagnosed with anxiety", "I've been diagnosed with anxiety", "I was just diagnosed with anxiety"]

    for comment in comment_list:
        for key, value in comment.items():
            text = value['text']
            flair_text = value['author_flair']
            for sentence in identify_list:
                if sentence in text:
                    with open('data/user_list/anxiety_user_list', mode='a', encoding='utf8') as file:
                        file.write(username+' [info] '+text+'\n')
                    return True
            if flair_text:
                pass
    return False

def _identify_background(username,comment):
    if not _identify_bipolar(username,comment) and not _identify_depression(username,comment):
        with open('data/user_list/background_user_list', mode='a', encoding='utf8') as file:
            file.write(username+' [info] [text]\n')
        return True
    else:
        return False

def _get_check_user_list(check_list):
    user_list = set()
    for type in check_list:
        with open('data/user_list/'+type+'_user_list', mode='r', encoding='utf8') as file:
            for line in file.readlines():
                user_list.add(line.split(' [info] ')[0])
    return user_list

def get_data_for_user(keyword):
    user_list = set()
    with open('data/user_list/'+keyword+'_user_list') as fp:
        for line in fp.readlines():
            user, _ = line.strip().split(' [info] ')
            user_list.add(user)
    for user in user_list:
        get_user_comments = GetUserCommentsFromPushshift(
            user, 1514782800)
        comment_list = get_user_comments.get_comments()
        with open('data/reddit/'+keyword+'/'+user, mode='a', encoding='utf8') as fp:
            for comment in comment_list:
                comment = json.dumps(comment)
                fp.write(comment + '\n')
    


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data_type', type=str, default='anxiety')
    args = parser.parse_args()
    os.chdir('/home/xiaobo/emotion_disorder_detection')
    key_words = args.data_type
    if key_words == 'bipolar':
        get_data = get_bipolar_data
    elif key_words == 'depression':
        get_data = get_depression_data
    elif key_words == 'anxiety':
        get_data = get_anxiety_data
    elif key_words == 'background':
        get_data = get_background_data

    if user_from_reddit:
        for i in range(1):
            get_data()
    else:
        get_data()
    # get_data_for_user('anxiety')

