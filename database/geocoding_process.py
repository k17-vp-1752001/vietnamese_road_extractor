import pymongo
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import re
import requests
import time
from dotenv import load_dotenv
import os
from shapely.geometry import shape, Point

from .connectionDB import Database

load_dotenv()
be_db_conn_str = os.getenv("BE_DB_CONNECTION_STRING")
be_db = Database(be_db_conn_str)

border_collection = be_db.get_collection("NODE_DB", "borders")
border_documents = list(border_collection.find({}))


def get_border(province_code, district_code, village_code, street_code):
    result = []
    if street_code:
        result = list(filter(lambda item: (item['provinceCode'] == province_code
                                           and item['districtCode'] == district_code
                                           and item['villageCode'] == village_code
                                           and item['streetCode'] == ""), border_documents))
    elif village_code:
        result = list(filter(lambda item: item['provinceCode'] == province_code
                                          and item['districtCode'] == district_code
                                          and item['villageCode'] == ""
                                          and item['streetCode'] == "", border_documents))
    elif district_code:
        result = list(filter(lambda item: item['provinceCode'] == province_code
                                          and item['districtCode'] == ""
                                          and item['villageCode'] == ""
                                          and item['streetCode'] == "", border_documents))

    return result


####################################################################################################
administrative_units = {'tỉnh': 'province',
                        'thành phố': 'city',
                        'thành phố trực thuộc trung ương': 'city',
                        'thành phố thuộc thành phố trực thuộc trung ương': 'city',
                        'quận': 'district',
                        'huyện': 'district',
                        'thị xã': 'town',
                        'thành phố thuộc tỉnh': 'city',
                        'phường': 'ward',
                        'xã': 'commune',
                        'đường': 'street'}

first_level_administrative = {
    'Tỉnh': ["Lai Châu", "Điện Biên", "Lào Cai", "Hà Giang", "Cao Bằng", "Lạng Sơn", "Yên Bái",
             "Tuyên Quang", "Bắc Kạn", "Thái Nguyên", "Sơn La", "Phú Thọ", "Vĩnh Phúc", "Bắc Ninh",
             "Bắc Giang", "Quảng Ninh", "Hòa Bình", "Hưng Yên", "Hải Dương", "Thái Bình", "Hà Nam",
             "Nam Định", "Ninh Bình", "Thanh Hóa", "Nghệ An", "Hà Tĩnh", "Quảng Bình", "Quảng Trị",
             "Thừa Thiên Huế", "Quảng Nam", "Quảng Ngãi", "Kon Tum", "Gia Lai", "Bình Định",
             "Phú Yên", "Đắk Lắk", "Đắk Nông", "Khánh Hòa", "Lâm Đồng", "Ninh Thuận", "Bình Thuận",
             "Bình Phước", "Tây Ninh", "Bình Dương", "Đồng Nai", "Bà Rịa – Vũng Tàu", "Long An",
             "Đồng Tháp", "Tiền Giang", "Bến Tre", "An Giang", "Vĩnh Long", "Kiên Giang",
             "Hậu Giang", "Trà Vinh", "Sóc Trăng", "Bạc Liêu", "Cà Mau"],
    'Thành phố': ["Hà Nội", "Hồ Chí Minh", "Hải Phòng", "Đà Nẵng", "Cần Thơ"]}


def pre_process_address(full_address: str):
    address = full_address.split(', ')

    for i in range(len(address)):
        for vi, en in administrative_units.items():
            if address[i].lower().startswith(vi):
                address[i] = re.sub(vi, '', address[i], flags=re.IGNORECASE).strip()
                if en != 'street':
                    if address[i].strip().lower() == u'thủ đức':
                        address[i] += ' ' + 'city'
                    elif not address[i].isnumeric():
                        address[i] += ' ' + en
                    else:
                        address[i] = en + ' ' + address[i]
                break
        address[i].strip()

    return ', '.join(address)


def remove_nominator(full_address: str):
    address = full_address.split(', ')

    for i in range(len(address)):
        for vi, en in administrative_units.items():
            if address[i].lower().startswith(vi):
                address[i] = re.sub(vi + ' ', '', address[i], flags=re.IGNORECASE)
                break
        address[i].strip()

    return ', '.join(address)


def remove_first_nominator(full_address: str):
    address = full_address.split(', ')

    for vi, en in administrative_units.items():
        if address[0].lower().startswith(vi):
            address[0] = re.sub(vi + ' ', '', address[0], flags=re.IGNORECASE)
            break
    address[0].strip()

    return ', '.join(address)


def add_nominator_first_level_adm(full_address: str):
    address = full_address.split(', ')

    for i in range(len(address)):
        for part in address[i]:
            if part in first_level_administrative['Tỉnh']:
                address[i] = 'Tỉnh ' + address[i]
            elif part in first_level_administrative['Thành phố']:
                address[i] = 'Thành phố ' + address[i]
        address[i].strip()

    return ', '.join(address)


####################################################################################################
geolocator = Nominatim(user_agent='geocoding')
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

browser_user_agent = {
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36 Edg/88.0.705.74"
}


def geocoding_process(document):
    result = None

    # print(document)

    address = add_nominator_first_level_adm(document['fullAddress'])

    if 'hồ chí minh' in address.lower():
        address = re.sub('Quận 2', 'Thành phố Thủ Đức', address, flags=re.IGNORECASE).strip()
        address = re.sub('Quận 9', 'Thành phố Thủ Đức', address, flags=re.IGNORECASE).strip()
        address = re.sub('Quận Thủ Đức', 'Thành phố Thủ Đức', address, flags=re.IGNORECASE).strip()

    second_address = remove_first_nominator(address)
    print(document['provinceCode'], document['districtCode'], document['villageCode'], document['streetCode'])
    border = get_border(document['provinceCode'], document['districtCode'], document['villageCode'],
                        document['streetCode'])

    g = None
    # print(border)
    if border:
        g = shape(border[0]['geometry'])
        # display(g)

    url = ' https://nominatim.openstreetmap.org/search?'
    query = {'q': address, 'format': 'json', 'countrycodes': 'vn'}
    # print(address)

    # first try
    response = requests.get(url=url, params=query, headers=browser_user_agent)
    time.sleep(5)
    if response.status_code == 200:
        # print(response.json())
        # print(address, response.json())
        if g is None:
            if response.json():
                return response.json()[0]
        else:
            for location in response.json():
                point = Point(float(location['lon']), float(location['lat']))
                if point.within(g):
                    return location
    # second try
    query['q'] = second_address

    response = requests.get(url=url, params=query, headers=browser_user_agent)

    time.sleep(5)
    if response.status_code == 200:
        # print(second_address, response.json())
        # print(response.json())
        if g is None:
            if response.json():
                return response.json()[0]
            else:
                return None

        for location in response.json():
            point = Point(float(location['lon']), float(location['lat']))
            if g is not None:
                if point.within(g):
                    return location
        return None

    return None

