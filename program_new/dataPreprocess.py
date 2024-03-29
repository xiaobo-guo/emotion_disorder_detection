import os
import logging
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
logging.getLogger("tensorflow").setLevel(logging.ERROR)
from nltk.tokenize import sent_tokenize
from official.nlp.bert import tokenization
from random import shuffle, choice, seed
import tensorflow as tf
import argparse
import numpy as np
import re
import json
import math
from scipy.spatial.distance import euclidean

from fastdtw import fastdtw
from nltk.stem.porter import PorterStemmer



# bert_model_dir = 'F:/pretrained-models/bert/wwm_cased_L-24_H-1024_A-16'
bert_model_dir = '/home/xiaobo/pretrained_models/bert/wwm_cased_L-24_H-1024_A-16'


def build_text_tfrecord(user_file_list, data_path_list, record_path, suffix_list = ['.before', '.after']):
    if not os.path.exists(record_path):
        os.mkdir(record_path)
    max_seq = 142
    user_set = set()
    bert_vocab_file = os.path.join(bert_model_dir, 'vocab.txt')
    tokenizer = tokenization.FullTokenizer(
        bert_vocab_file, do_lower_case=False)

    with open(user_file_list, mode='r') as fp:
        for line in fp.readlines():
            user_set.add(line.split(' [info] ')[0])
    user_count = 0
    for i, user in enumerate(user_set):
        for suffix in suffix_list:
            file_name = os.path.join(data_path_list, user + suffix)
            record_file = user + suffix + ".tfrecord"
            record_file = os.path.join(record_path, record_file)
            if not os.path.exists(file_name):
                if suffix == '.after':
                    print(user)
                continue
            if os.path.exists(record_file):
                continue
            with open(file_name, mode='r', encoding='utf8') as fp:
                data = dict()
                text_data = dict()
                for line in fp.readlines():
                    try:
                        for id, value in json.loads(line.strip()).items():
                            feature, text = _prepare_reddit_text_id(
                                value['text'], tokenizer, max_seq)
                            data[id] = feature
                            text_data[id] = text
                    except json.decoder.JSONDecodeError:
                        pass
            writer = tf.io.TFRecordWriter(record_file)
            for id, feature in data.items():
                for sentence_feature in feature:
                    text_ids, text_mask, segment_ids = sentence_feature
                    example = tf.train.Example(
                        features=tf.train.Features(
                            feature={
                                "id": tf.train.Feature(bytes_list=tf.train.BytesList(value=[bytes(id, encoding='utf-8')])),
                                "text_ids": tf.train.Feature(int64_list=tf.train.Int64List(value=text_ids)),
                                "text_mask": tf.train.Feature(int64_list=tf.train.Int64List(value=text_mask)),
                                "segment_ids": tf.train.Feature(int64_list=tf.train.Int64List(value=segment_ids)),
                            }
                        )
                    )
                    writer.write(example.SerializeToString())
            writer.close()
        user_count += 1
        if user_count % 100 == 0:
            print(user_count)
    print('finish')


def build_multi_class_tfrecord(data_path_list, record_path, type_list=["train", "valid", "test"]):

    bert_vocab_file = os.path.join(bert_model_dir, 'vocab.txt')
    tokenizer = tokenization.FullTokenizer(
        bert_vocab_file, do_lower_case=False)
    count_list = [0 for _ in range(len(data_path_list))]
    tweet_list = [[] for _ in range(len(data_path_list))]
    meta_data = dict()

    meta_data['classes'] = 2
    meta_data['class_weight_list'] = [0, 0]
    meta_data['class_weight'] = dict()

    if not os.path.exists(record_path):
        os.mkdir(record_path)
    max_seq_length = 142
    text_set = set()
    for type, data_path in enumerate(data_path_list):
        with open(data_path, encoding='utf8') as source:
            for line in source.readlines():
                try:
                    data = line.strip().split('\t')
                    if data[0] == 'ID':
                        continue
                    text = data[1]
                    # label = data[2:7] + data[-3:]
                    label = [data[-2]]
                    for i in range(len(label)):
                        label[i] = int(label[i])
                        if type == 0:
                            meta_data['class_weight_list'][label[i]] += 1
                    if _clean_text(text) not in text_set:
                        text_set.add(_clean_text(text))
                        text = _prepare_text_id(
                            text, tokenizer, max_seq_length)
                        if text is None:
                            continue
                        tweet_list[type].append(
                            (text, label))
                        count_list[type] += 1
                except:
                    continue
        seed(123)
        shuffle(tweet_list[type])

    for index, data in enumerate(tweet_list):
        print(type_list[index] + " : " + str(len(data)))
        meta_data[type_list[index]+'_size'] = len(data)
        record_file = type_list[index]+".tfrecord"
        record_file = os.path.join(record_path, record_file)
        writer = tf.io.TFRecordWriter(record_file)
        for index, tweet in enumerate(data):
            (text_ids, text_mask, segment_ids, text), label = tweet
            example = tf.train.Example(
                features=tf.train.Features(
                    feature={
                        "label": tf.train.Feature(int64_list=tf.train.Int64List(value=label)),
                        "text_ids": tf.train.Feature(int64_list=tf.train.Int64List(value=text_ids)),
                        "text_mask": tf.train.Feature(int64_list=tf.train.Int64List(value=text_mask)),
                        "segment_ids": tf.train.Feature(int64_list=tf.train.Int64List(value=segment_ids)),
                        "text": tf.train.Feature(bytes_list=tf.train.BytesList(value=[bytes(text, encoding='utf-8')])),
                    }
                )
            )
            writer.write(example.SerializeToString())
        writer.close()

    basic_weight = max(meta_data['class_weight_list'])
    for i, weight in enumerate(meta_data['class_weight_list']):
        meta_data['class_weight_list'][i] = basic_weight / \
            meta_data['class_weight_list'][i]
    meta_file = os.path.join(record_path, 'meta_data')
    with open(meta_file, mode='w', encoding='utf8') as fp:
        json.dump(meta_data, fp)


def build_binary_tfrecord(data_path_list, record_path, label_index, type_list=["train", "valid", "test"], balanced=True):

    bert_vocab_file = os.path.join(bert_model_dir, 'vocab.txt')
    tokenizer = tokenization.FullTokenizer(
        bert_vocab_file, do_lower_case=False)
    count_list = [[0, 0] for _ in range(len(data_path_list))]
    tweet_list = [[[], []] for _ in range(len(data_path_list))]
    meta_data = dict()

    meta_data['classes'] = 2
    meta_data['class_weight_list'] = [0, 0]
    meta_data['class_weight'] = dict()

    if not os.path.exists(record_path):
        os.mkdir(record_path)
    max_seq_length = 142
    text_set = set()
    for type, data_path in enumerate(data_path_list):
        with open(data_path, encoding='utf8') as source:
            for line in source.readlines():
                try:
                    data = line.strip().split('\t')
                    if data[0] == 'ID':
                        continue
                    text = data[1]
                    label = data[2:7] + data[-3:]
                    label = [label[label_index]]
                    for i in range(len(label)):
                        label[i] = int(label[i])
                        if type == 0:
                            meta_data['class_weight_list'][label[i]] += 1
                    if _clean_text(text) not in text_set:
                        text_set.add(_clean_text(text))
                        text = _prepare_text_id(
                            text, tokenizer, max_seq_length)
                        if text is None:
                            continue
                        tweet_list[type][label[0]].append(
                            (text, label))
                        count_list[type][label[0]] += 1
                except:
                    continue
        seed(123)
        shuffle(tweet_list[type][0])
        shuffle(tweet_list[type][1])
        if balanced:
            count_list[type] = min(count_list[type])
            meta_data['class_weight_list'] = [count_list[0], count_list[0]]
        tweet_list[type] = tweet_list[type][0][:count_list[type]] + \
            tweet_list[type][1][:count_list[type]]
        shuffle(tweet_list[type])

    for index, data in enumerate(tweet_list):
        print(type_list[index] + " : " + str(len(data)))
        meta_data[type_list[index]+'_size'] = len(data)
        record_file = type_list[index]+".tfrecord"
        record_file = os.path.join(record_path, record_file)
        writer = tf.io.TFRecordWriter(record_file)
        for index, tweet in enumerate(data):
            (text_ids, text_mask, segment_ids, text), label = tweet
            example = tf.train.Example(
                features=tf.train.Features(
                    feature={
                        "label": tf.train.Feature(int64_list=tf.train.Int64List(value=label)),
                        "text_ids": tf.train.Feature(int64_list=tf.train.Int64List(value=text_ids)),
                        "text_mask": tf.train.Feature(int64_list=tf.train.Int64List(value=text_mask)),
                        "segment_ids": tf.train.Feature(int64_list=tf.train.Int64List(value=segment_ids)),
                        "text": tf.train.Feature(bytes_list=tf.train.BytesList(value=[bytes(text, encoding='utf-8')])),
                    }
                )
            )
            writer.write(example.SerializeToString())
        writer.close()

    basic_weight = max(meta_data['class_weight_list'])
    for i, weight in enumerate(meta_data['class_weight_list']):
        meta_data['class_weight_list'][i] = basic_weight / \
            meta_data['class_weight_list'][i]
    meta_file = os.path.join(record_path, 'meta_data')
    with open(meta_file, mode='w', encoding='utf8') as fp:
        json.dump(meta_data, fp)


def _prepare_text_id(text, tokenizer, max_seq_length):
    text = ' '.join(text.split())
    text = text.strip()
    text_tokens = tokenizer.tokenize(text)
    if len(text_tokens) > max_seq_length:
        text_tokens = text_tokens[0: (max_seq_length - 2)]
    tokens = []
    segment_ids = []
    tokens.append("[CLS]")
    segment_ids.append(0)
    for token in text_tokens:
        tokens.append(token)
        segment_ids.append(0)
    tokens.append("[SEP]")
    segment_ids.append(0)

    input_ids = tokenizer.convert_tokens_to_ids(tokens)

    input_mask = [1] * len(input_ids)

    text = '[CLS] ' + text + ' [SEP]'

    while len(input_ids) < max_seq_length:
        input_ids.append(0)
        input_mask.append(0)
        segment_ids.append(0)

    assert len(input_ids) == max_seq_length
    assert len(input_mask) == max_seq_length
    assert len(segment_ids) == max_seq_length

    return (input_ids, input_mask, segment_ids, text)


def _prepare_reddit_text_id(text, tokenizer, max_seq_length):
    data_list = []
    original_text_list = []
    text_list = []
    text = ' '.join(text.split())
    text = text.strip()
    text_list = sent_tokenize(text)
    # for s_str in text.split('.'):
    #     if '?' in s_str:
    #         text_list.extend(s_str.split('?'))
    #     elif '!' in s_str:
    #         text_list.extend(s_str.split('!'))
    #     else:
    #         text_list.append(s_str)
    for text in text_list:
        if text == '':
            continue
        text = ' '.join(text.split())
        text = text.strip()
        text_tokens = tokenizer.tokenize(text)
        if len(text_tokens) > max_seq_length - 2:
            text_tokens = text_tokens[0: (max_seq_length - 2)]
        tokens = []
        segment_ids = []
        tokens.append("[CLS]")
        tokens.extend(text_tokens)
        tokens.append("[SEP]")

        input_ids = tokenizer.convert_tokens_to_ids(tokens)

        input_mask = [1] * len(input_ids)
        segment_ids = [0] * len(input_ids)

        text = '[CLS] ' + text + ' [SEP]'

        while len(input_ids) < max_seq_length:
            input_ids.append(0)
            input_mask.append(0)
            segment_ids.append(0)

        assert len(input_ids) == max_seq_length
        assert len(input_mask) == max_seq_length
        assert len(segment_ids) == max_seq_length
        feature = (input_ids, input_mask, segment_ids)
        data_list.append(feature)
        original_text_list.append(text)

    return data_list, original_text_list


def _clean_text(original_tweet):
    processed_tweet = re.sub(r'http[^ ]+', 'URL', original_tweet)
    processed_tweet = re.sub(r'RT @[^ ]+ ', '', processed_tweet)
    processed_tweet = re.sub(r'rt @[^ ]+ ', '', processed_tweet)
    processed_tweet = processed_tweet.replace('\n', ' ')
    processed_tweet = processed_tweet.replace('\r', '')
    processed_tweet = processed_tweet.replace('RT', '')
    processed_tweet = processed_tweet.replace('rt', '')
    processed_tweet = re.sub(r' +', ' ', processed_tweet)
    processed_tweet = processed_tweet.strip()
    return processed_tweet


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root_dir', type=str, required=True)
    parser.add_argument('--data_type', choices=['background', 'anxiety', 'bipolar', 'depression'], type=str, default='background')
    parser.add_argument('--function_type', choices=['build_text_tfrecord'], type=str, default='build_text_tfrecord')
    parser.add_argument('--window_size', type=int)
    parser.add_argument('--step_size', type=float)

    args = parser.parse_args()
    root_dir = args.root_dir
    keywords = args.data_type
    window_size = args.window_size
    step_size = args.step_size

    function = args.function_type
    os.chdir(root_dir)
    if function == 'build_text_tfrecord':
        build_text_tfrecord('./data/user_list/' + keywords + '_user_list',
                            './data/reddit/' + keywords, './data/TFRecord/reddit_data/' + keywords)
    elif function == 'build_binary_tfrecod':
        pass
    elif function == 'build_multi_class_tfrecord':
        pass
