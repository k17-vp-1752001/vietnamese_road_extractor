#!/usr/bin/python
# -*- coding: utf-8 -*-

import codecs
import re
from operator import itemgetter
import os
from dotenv import load_dotenv

import newspaper
import unidecode
from fuzzywuzzy import process, fuzz
from nltk import sent_tokenize, word_tokenize
from vncorenlp import VnCoreNLP

from database.connectionDB import Database
from database.update_database import update, get_undone_article_list
from news_extractor.extractor import extract_text

load_dotenv()
be_db_connection_string = os.getenv('BE_DB_CONNECTION_STRING')

backend_db = Database(be_db_connection_string)
db = backend_db.connect_database("NODE_DB")

browser_user_agent = {
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36 Edg/88.0.705.74"
}

config = newspaper.Config()
config.browser_user_agent = browser_user_agent.get('User-Agent')
config.request_timeout = 10

province = [item["fullAddress"] for item in db['areas'].find({'type': 1})]
district = [item["fullAddress"] for item in db['areas'].find({'type': 2})]
street = [item["fullAddress"] for item in db['areas'].find({'type': 4})]

street_code = [(item["streetCode"], item["districtCode"], item["provinceCode"]) for item in
               db['areas'].find({'type': 4})]

backend_db.close()


# vncorenlp_file = r'../VnCoreNLP/VnCoreNLP-1.1.1.jar'
# vncorenlp = VnCoreNLP(vncorenlp_file, annotators="wseg,pos,ner,parse", max_heap_size='-Xmx2g')


def read_file(file):
    with open(file, 'r', encoding='utf-8') as reader:
        return reader.readlines()


def create_stopword_list(file_dir='vietnamese-stopwords.txt'):
    f = codecs.open(os.path.join(os.path.dirname(__file__), file_dir), encoding='utf-8')
    data = []
    for i, line in enumerate(f):
        line = repr(line)
        line = line[1:len(line) - 3]
        data.append(line)
    return data


stopword_vn = create_stopword_list()


def normalize(string: str):
    compress = ' '.join(string.replace('-', ' ').split())
    return unidecode.unidecode(compress.lower().replace(' ', '-'))


def standardize_data(row):
    """
    Remove special characters and compress white spaces
    """
    # nltk.download('punkt')
    row = ''.join(char if char.isalnum() or char in [' ', ',', '-', '.', '\n'] else '' for char in row)
    return ' '.join(row.split())


def add_to_count_list(count_list, name):
    search = next((item for item in count_list if name in item['name']), None)
    if search is None:
        count_list.append({'name': name, 'count': 1})
    else:
        search['count'] += 1


def convert_to_street_code(street_full_address: str):
    address = street_full_address.strip().split(',')
    street_name = address[0].strip()
    district_name = address[1].strip()
    province_name = address[2].strip()
    return normalize(street_name), normalize(district_name), normalize(province_name)


def extract_article(link: str):
    pattern = re.compile(u"ảnh:", re.IGNORECASE)

    content = ''
    article = newspaper.Article(url=link.strip(), language='vi', config=config)
    try:
        article.download()
        article.parse()
        if re.search(u'mưa', article.text, re.IGNORECASE):
            print(link)
            content += pattern.sub(" ", article.meta_description + " " + article.text)
    except newspaper.article.ArticleException:
        print('{link} retrieve failed'.format(link=link))
        return 'Failed'

    print('Done extracting')

    return content


def location_extract(text: str):
    """
    :param text: str
    :return: list of unique location
    """
    location_list = []
    location_count = []

    # Get stopwords list for vietnamese from prepared file

    # Sentence tokenization
    text += '.'
    sentences = sent_tokenize(text)

    # VNCoreNLP

    # annotator = VnCoreNLP("VnCoreNLP-master/VnCoreNLP-1.1.1.jar", annotators="wseg,pos,ner", max_heap_size='-Xmx2g')

    with VnCoreNLP(address='http://127.0.0.1', port=9000) as vncorenlp:
        # with VnCoreNLP(vncorenlp_file) as vncorenlp:
        for sentence in sentences:
            if not sentence:
                continue

            sentence = sentence.replace('(', ',').replace(')', ',')
            sentence = standardize_data(sentence)

            words_token = [word for word in word_tokenize(sentence) if word not in stopword_vn]
            # print(words_token)

            # standardize_text = standardize_data(" ".join(words_token))
            standardize_text = " ".join(words_token)
            if not standardize_text:
                continue

            token = vncorenlp.ner(standardize_text)

            word_list = [item[0].replace("_", " ") for sublist in token for item in sublist]
            word_type_list = [item[1] for sublist in token for item in sublist]

            i = 0
            loc_temp = ''

            while i in range(len(word_list)):
                word = word_list[i]
                word_type = word_type_list[i]

                # named entity recognize
                # PER: Person
                # ORG: Organisation
                # LOC: Location <<<<
                # O: other
                # B-LOC: begin location
                # I-LOC: inner location
                # đường Hồ Chí Minh
                # B-LOC     I-LOC
                # [(token, type)]

                # if any(sub in word_type for sub in ('B-PER', 'B-LOC')):
                if word_type == 'B-LOC':
                    if len(loc_temp) > 0:
                        location_list.append(loc_temp.strip())
                        add_to_count_list(count_list=location_count, name=loc_temp.strip())
                    loc_temp = word
                    i += 1
                # elif any(sub in word_type for sub in ('I-PER', 'I-LOC')):
                elif word_type == 'I-LOC':
                    # while i < len(word_type_list) and any(sub in word_type_list[i] for sub in ('I-LOC', 'I-PER')):
                    while i < len(word_type_list) and word_type_list[i] == 'I-LOC':
                        loc_temp += ' ' + word_list[i]
                        i += 1
                else:
                    if len(loc_temp) > 0:
                        location_list.append(loc_temp.strip())
                        add_to_count_list(count_list=location_count, name=loc_temp.strip())
                    loc_temp = ''
                    i += 1

            if len(loc_temp) > 0:
                location_list.append(loc_temp.strip())
                add_to_count_list(count_list=location_count, name=loc_temp.strip())

        vncorenlp.close()

    return set(location_list)


def match_road_name(location_set):
    province_items = []
    district_items = []
    street_items = []

    for location in location_set:
        location = ' '.join(location.split())
        location = location.replace("TP. ", "TP.") \
            .replace("TP .", "TP.") \
            .replace("TP ", "TP") \
            .replace("TP", "TP.") \
            .replace("TP.", u"Thành phố ") \
            .replace("Q. ", "Q.") \
            .replace("Q ", "Q.") \
            .replace("Q.", u"Quận ") \
            .replace("H. ", "H.") \
            .replace("H ", "H,") \
            .replace("H.", u"Huyện ") \
            .replace("tx", "TX") \
            .replace("TX. ", u"Thị xã") \
            .replace("TX ", u"Thị xã") \
            .replace(u"tỉnh ", "") \
            .replace(u"Tỉnh ", "")

        if any(substr in location.lower() for substr in ("hcm", "thành phố hồ chí minh")):
            closest = "Hồ Chí Minh"
            province_items.append("Hồ Chí Minh")
        elif "Hà Nội" in location:
            closest = "Hà Nội"
            province_items.append("Hà Nội")
        elif "Đà Nẵng" in location:
            closest = "Đà Nẵng"
            province_items.append("Đà Nẵng")
        elif "Hải Phòng" in location:
            closest = "Hải Phòng"
            province_items.append("Hải Phòng")
        elif "Cần Thơ" in location:
            closest = "Cần Thơ"
            province_items.append("Cần Thơ")
        else:
            province_guess = process.extract(location, province, scorer=fuzz.partial_ratio, limit=len(province))
            district_guess = process.extract(location, district, scorer=fuzz.partial_ratio, limit=len(district))
            street_guess = process.extract(location, street, scorer=fuzz.partial_ratio, limit=len(street))
            matches = []
            for item in province_guess + district_guess + street_guess:
                norm_location = normalize(location)
                norm_item = normalize(item[0].split(',')[0])
                if norm_location in norm_item:
                    matches.append(item)

            if len(matches) > 0:
                closest = max(matches, key=itemgetter(1))[0]

                if closest in province:

                    province_items.append(closest)
                elif closest in district:
                    district_items.append(closest)
                else:
                    street_items.append(closest)
            else:
                closest = "Unknown"
        print(location + ' - ', closest)

    # print(set(province_items))
    # print(set(district_items))
    # print(set(street_items))
    # print()
    road_list = []

    for street_item in set(street_items):
        address = street_item.split(',')
        street_pattern = address[0].strip()
        added_district = False
        for district_item in set(district_items):
            district_address = district_item.split(',')
            district_pattern = district_address[0].strip()
            province_pattern = district_address[1].strip()
            added_district = True
            added_province = False
            for province_item in set(province_items):
                province_pattern = province_item.strip()
                added_province = True
                full_address = ', '.join([street_pattern, district_pattern, province_pattern])

                if convert_to_street_code(full_address.strip()) in street_code:
                    # print(full_address)
                    road_list.append(full_address.strip())

            if not added_province:
                full_address = ', '.join([street_pattern, province_pattern, province_pattern])

                if convert_to_street_code(full_address.strip()) in street_code:
                    # print(full_address)
                    road_list.append(full_address.strip())

        if not added_district:
            district_pattern = address[1].strip()
            added_province = False
            for province_item in set(province_items):
                province_pattern = province_item.strip()
                added_province = True
                full_address = ', '.join([street_pattern, district_pattern, province_pattern])

                if convert_to_street_code(full_address.strip()) in street_code:
                    # print(full_address)
                    road_list.append(full_address.strip())
            if not added_province:
                # print(convert_to_street_code(address.strip()))
                if convert_to_street_code(', '.join(address)) in street_code:
                    # print(', '.join(address))
                    road_list.append(', '.join(address))

    print("Done")
    return set(road_list)


def road_extract(article):
    text = article['text']
    location_names = location_extract(text)
    road_set = match_road_name(location_set=location_names)
    return road_set


# articles = read_file('articles.txt')

def extract_article_list(articles):
    result = []
    articles_done = []
    with open("results.txt", 'w', encoding='utf-8') as result_writer, \
            open("done.txt", 'w', encoding='utf-8') as article_writer:
        for article in articles:
            road_set = road_extract(article)
            result.extend(road_set)
            result_writer.write('\n'.join(road_set) + '\n')
            result_writer.flush()
            articles_done.append(article)
            article_writer.write(article['url'])
            article_writer.flush()
            print(len(result))
            update(article, list(road_set))

    return result, articles_done


def run():
    article_list = get_undone_article_list()
    if article_list:
        extract_article_list(article_list)


# extract_article_list(articles)
# vncorenlp.close()

# test
url = "https://tuoitre.vn/mua-nhu-trut-suot-buoi-sang-dan-sai-gon-bi-bom-dat-xe-chet-may-qua-diem-ngap-20210525094718133.htm"
article = {'url': url}
article.update({'text': extract_text(article['url'])})

extract_article_list([article])
