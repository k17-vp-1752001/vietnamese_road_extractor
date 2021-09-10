import re
import newspaper
import nltk
from datetime import datetime, date

browser_user_agent = {
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36 Edg/88.0.705.74"
}

config = newspaper.Config()
config.browser_user_agent = browser_user_agent.get('User-Agent')
config.request_timeout = 10


def extract_text(url, keyword=None):

    if keyword is None:
        keyword = []

    article = newspaper.Article(url=url, language='vi', config=config)
    pattern = re.compile(u"ảnh:", re.IGNORECASE)

    result = ""
    publish_date = datetime.now()
    try:
        article.download()
        article.parse()
        # print(article.publish_date)
        publish_date = article.publish_date
        # print(publish_date)
        if keyword:
            if all(re.search(kw, article.text, re.IGNORECASE) for kw in keyword):
                # print(url)
                result += pattern.sub(" ", article.meta_description + " " + article.text)
        else:
            result += pattern.sub(" ", article.meta_description + " " + article.text)
    except newspaper.article.ArticleException:
        print('{link} retrieve failed'.format(link=url))

    return result


# print(extract_text("https://tuoitre.vn/nha-trang-mua-dau-mua-duong-bien-thanh-song-440257.htm"))
