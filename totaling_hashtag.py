import sys
import requests
import time as t
import pandas as pd
import logging
import MeCab
from collections import Counter

m = MeCab.Tagger("-Ochasen")

class InstaTool():
    def __init__(self, instaID, ACCESS_TOKEN, query, wait_time=30):
        self.instaID = instaID
        self.ACCESS_TOKEN = ACCESS_TOKEN
        self.query = query
        self.df = pd.DataFrame({'count':[0]},index=[pd.Timestamp.now()])
        self.target_words = []
        self.word_flag = False
        self.run_flag = True
        self.wait_time = wait_time
        self.next_url = ""

    def start(self):
        while True:
            logger.info("get | set | run | close")
            str = input("input>>>")
            if (str == "get"):
                logger.info("How many words?(int)")
                num_s = input("input>>>")
                if not (num_s.isdecimal()):
                    logger.warning("not int!")
                    continue
                num = int(num_s)
                self.get_com_word(num)
            elif str == "set":
                logger.info("target word:{}".format(self.target_words))
                logger.info("clean your target words?(y/n)")
                r = input()
                if r == "y":
                    self.target_words = []
                elif r == "n":
                    pass
                else:
                    logger.warning("illegal word!")
                logger.info("add words >>> (?, ?, ?, ,,,)")
                word = input("input>>>")
                word_l = word.strip().split(",")
                logger.info("add {} ? (y/n)".format(word_l))
                r = input()
                if r == "y":
                    self.target_words.extend(word_l)
                elif r == "n":
                    pass
                logger.info("target word:{}".format(self.target_words))
            elif str == "run":
                self.run().to_csv("{}_daily_data.csv".format(query))
                df_week = self.df.resample('W').sum()
                df_week.to_csv("{}_week_data.csv".format(query))
            elif str == "close":
                logger.info("close InstaTool")
                break
            else:
                logger.warning("illegal word!")

    def get_hash_url(self, serch_type="top_media", lim = 50):
        id_search_url = "https://graph.facebook.com/v12.0/ig_hashtag_search?user_id=" + self.instaID + "&q=" + self.query +  "&access_token=" + self.ACCESS_TOKEN
        response = requests.get(id_search_url)
        hash = response.json()
        logger.debug("hash_id:{}".format(hash))
        try:
            hash_id = hash['data'][0]['id']
            url = "https://graph.facebook.com/" + hash_id + "/" + serch_type + "?user_id=" + instaID + "&q=" + self.query + "&access_token=" + ACCESS_TOKEN + "&fields=caption,timestamp&limit=" + str(lim)
            logger.debug("url to get data:{}".format(url))
            return url
        except KeyError:
            logger.error("cannot get a hash tag ID\nRESPONSE:\n{}".format(hash))
            sys.exit()

    def get_data(self, url):
        response = requests.get(url)
        json_data = response.json()
        count = 0
        while not ('data' in json_data):
            logger.warning("API Error. wait now and tyr again.")
            t.sleep(610)
            response = requests.get(url)
            json_data = response.json()
            count += 1
            if count > 10:
                logger.info("totaling all data")
                self.run_flag = False
                break
        return json_data

    def set_data(self, df, time):
        idx = -1
        for d_time in df.index.values:
            idx += 1
            if time > d_time:
                pass
            elif time == d_time:
                df.at[time,'count'] +=1
                break
            elif time < d_time:
                pd_insert = pd.DataFrame({'count':[1]},index=[time])
                df = pd.concat([df[:idx], pd_insert, df[idx:]])
                break
        return df

    # totaling "data" (not json)
    def totaling_data(self, data):
        df = self.df
        try:
            logger.info("totaling data:{}".format(data["timestamp"]))
            time = pd.to_datetime(data["timestamp"][:10])
            self.df = self.set_data(df, time)
        except KeyError:
            logger.warning("KeyError: 'timestamp'")

    # totaling json data
    def totaling(self, json_data):
        for data in json_data["data"]:
            try:
                if self.word_flag and self.match_data(data["caption"]):
                    logger.debug("skip totaling:{}".format(data["timestamp"]))
                    continue
                self.totaling_data(data)
            except KeyError:
                logger.warning("KeyError: 'caption'")
                continue
        try:
            # get new data
            new_data = json_data["paging"]["next"]
            return new_data
        except KeyError:
            logger.warning("missed getting next_data")
            sys.exit()

    def run(self, max_times=100):
        url = self.get_hash_url()
        json_data = self.get_data(url)
        count = 0
        pre_data = ""
        if len(self.target_words) > 0:
            self.word_flag = True
        logger.info("start totaling")
        logger.info("stop run by ctrl-c")
        try:
            while self.run_flag:
                logger.info("totaling {}th data set now".format(count))
                self.next_url = self.totaling(json_data)
                count += 1
                logger.debug("check first data:\n{}".format(json_data["data"][0]["caption"]))
                # check if updateing data three times.
                for i in range(3):
                    # To avoid the access limit of Instagram API
                    t.sleep(self.wait_time)
                    json_data = self.get_data(self.next_url)
                    if pre_data != json_data["data"][0]:
                        pre_data = json_data["data"][0]
                        break
                    elif i == 2:
                        self.run_flag = False
                        logger.warning("not updating data")
                if count > max_times:
                    self.run_flag = False
                    logger.warning("reach the predatemined num of times")

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt")
        logger.info("Last url:\n{}".format(self.next_url))
        logger.info("finish")
        return self.df

    def analyze_word(self, caption):
        logger.debug("word analyzing")
        caption = caption.replace("\n", "")
        node = m.parseToNode(caption)
        word = []
        while node:
            part = node.feature.split(",")[0]
            if part in ["名詞", "動詞", "形容詞"]:
                origin = node.feature.split(",")[6]
                word.append(origin)
            node = node.next
        word = [s for s in word if "*" != s]
        return word

    def count_word(self, words, word_num=150):
        c_word = Counter(words)
        return c_word.most_common(word_num)

    def get_com_word(self, num):
        words = []
        url = self.get_hash_url()
        json_data = self.get_data(url)
        for data in json_data["data"]:
            words.extend(self.analyze_word(data["caption"]))
        common_word = self.count_word(words, word_num=num)
        logger.info("common words on #query:\n{}".format(common_word))
        return [key[0] for key in common_word]

    # param: json_data["caption"]
    # return: if not match => True; else => False
    def match_data(self, caption):
        flag = True
        if len(self.target_words) < 1:
            logger.warning("common_words are not seted")
        words = self.analyze_word(caption)
        for t_w in self.target_words:
            for w in words:
                if w == t_w:
                    flag = False
                    break
        return flag

########################
instaID = ""
ACCESS_TOKEN = ""
########################

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    logger = logging.getLogger(__name__)
    args = sys.argv
    query = args[1]
    Insta = InstaTool(instaID, ACCESS_TOKEN, query)
    Insta.target_words.extend(["ランチ", "美味しい", "名古屋", "しゃぶしゃぶ", "食べる", "肉", "すき焼き", "食い始め", "ご飯", "料理", "ディナー", "寿司", "海鮮", "いただく", "弁当", "丼", "お祝い", "和牛"])
    # Insta.get_com_word(150)
    Insta.start()
