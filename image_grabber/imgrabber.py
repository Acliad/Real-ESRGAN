import random
import requests
import os
import re
import imghdr
import logging
import urllib.parse, urllib.error
from bs4 import BeautifulSoup
from requests.api import head

GOOGLE_SEARCH_BASE_URL = "https://www.google.com/search"
URL_REGEX_PATTERN = '\["(?:https:|http[^"]*?)", *\d+, *\d+\], *\["(https:|http[^"]*?)", *\d+, *\d+\]'
URL_SEARCH_WORDS_KEY_ANY = "as_oq"
URL_SEARCH_WORDS_KEY_ALL = "as_q"
DEFAULT_HEADERS = {
    "User-Agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
}
DEFAULT_PAYLOAD = {
    URL_SEARCH_WORDS_KEY_ANY: "",
    URL_SEARCH_WORDS_KEY_ALL: "",
    "tbm": "isch",
    "safe": "images",
    "tbs": "isz:lt,islt:10mp",
}


class ImGrabber:
    """A class for searching and downloading images from Google Images"""

    def __init__(self, words=None, headers=DEFAULT_HEADERS, payload=DEFAULT_PAYLOAD) -> None:
        """Construct an ImGrabber instance for searching and downloading images from Google Images

        Args:
            words (list, optional): List of string words to use for image search
            headers (dict, optional): header used for get request
            payload (dict, optional): payload used for get request
        """
        self.words = words
        self.payload = payload
        self.headers = headers
        self.links = []
        self.search_url = ''
        self.logger = logging.getLogger(__name__)


    def search(self, words=None, type='all'):
        """Perform an image search and get the links to the first 100 photos in the search

        Args:
            words (list, optional): List of string words to use for image search. If None, uses instance's words list
            type (str, optional): Type of search to use for words. Can be 'any' or 'all'. 'all' implies OR between each
                                  keyword search

        Returns:
            list: list of links to photos in search (copy of self.links)
        """
        if words is None:
            words = self.words

        payload = self.payload
        if type == 'any':
            payload[URL_SEARCH_WORDS_KEY_ANY] = " ".join(words)
        elif type == 'all':
            payload[URL_SEARCH_WORDS_KEY_ALL] = " ".join(words)
        else:
            raise ValueError("Type argument must be 'any' or 'all'. Got " + str(type))

        payload_str = urllib.parse.urlencode(payload, safe=':,')
        r = requests.get(GOOGLE_SEARCH_BASE_URL, params=payload_str, headers=self.headers)
        self.search_url = r.url
        soup = BeautifulSoup(r.text, 'lxml')
        scripts = soup.select('script')
        self.links = re.findall(URL_REGEX_PATTERN, str(scripts))

        return self.links.copy()

    def searchrdm(self, k, words=None, type='all'):
        """Perform an image search using a random selection of words. Selects k random words from words or self.words

        Args:
            k (int): number of words to select
            words (list, optional): list of words to choose from. If words==None, uses self.words
            type (str, optional): Type of search to use for words. Can be 'any' or 'all'. 'all' implies OR between each
                                  keyword search
        """
        if words is None:
            words = self.words

        search_words = random.choices(words, k=k)
        self.search(words=search_words, type=type)

        return search_words

    def download(self, destination, links=None, prefix='', suffix='', start=0, zfill=0, maximgs=100):
        """Download images to destination

        Args:
            destination (str): folderpath to download to
            links (list, optional): list of links to images to download. Defaults to None.
            prefix (str, optional): image file prefix. Defaults to ''.
            suffix (str, optional): image file suffix. Defaults to ''.
            start (int, optional): number to start file numbering with. Defaults to 0.
            zfill (int, optional): number of zeros to fill image filename with. Defaults to 0.
            maximgs (int, optional): max number of images to download. Defaults to 100.

        Returns:
            [type]: [description]
        """
        if links == None:
            links = self.links

        i = 0
        for link in links:
            try:
                # Assemble path and request image
                img_name = prefix + str(i + start).zfill(zfill) + suffix
                img_path = destination + '/' + img_name
                r = requests.get(link, headers=self.headers, stream=True)

                # Check status code and write file
                if r.status_code == 200: # Success code
                    # Write image date to file
                    with open(img_path, 'wb') as img:
                        for chunk in r:
                            img.write(chunk)

                    # Check the image and add the file extension
                    img_type = imghdr.what(img_path)
                    if img_type is not None:
                        os.rename(img_path, img_path + '.' + img_type)
                        # print("Saved " + img_path + '.' + img_type)
                        self.logger.debug("Saved " + img_path + '.' + img_type)
                        i += 1
                    else:
                        # print("Not a known image type, skipping...")
                        self.logger.warning("Not a known image type (from {}\) skipping...".format(link))
                        os.remove(img_path)

                else: # Got an error
                    # print("Got: HTTP Error " + str(r.status_code))
                    # print("Link: " + link)
                    # print("Skipping...")
                    self.logger.error("Got: HTTP Error " + str(r.status_code) + " from link " + link)

            except Exception as err:
                # print("Unhandled Error: " + str(err))
                # print("Continuing...")
                self.logger.exception(err)

            if i == maximgs:
                break

        return i

    def grabrdm(self, destination, n, k, type='all', links=None, prefix='', suffix='', zfill=0):

        n_downloaded = 0
        while n_downloaded < n:
            search_words = self.searchrdm(k, type=type)
            # print("Search: " + ' '.join(search_words))
            words_str = ' '.join(search_words) if type == 'all' else ' OR '.join(search_words)
            self.logger.info("Search: " + words_str)
            n_downloaded += self.download(
                destination,
                links=links,
                prefix=prefix,
                suffix=suffix,
                start=n_downloaded,
                zfill=zfill,
                maximgs=(n - n_downloaded))

if __name__ == "__main__":
    import shutil

    NOUNS_PATH = "./image_grabber/nounlist.txt"
    IMAGES_ROOT_PATH = "./image_grabber/images/"
    NUM_SEARCH_WORDS  = 3
    NUM_FOLDERS       = 3
    IMAGES_PER_FOLDER = 10
    RESUME            = True

    with open(NOUNS_PATH) as words_file:
        words = [word.strip() for word in words_file.readlines()]

    crawler = ImGrabber(words)
    formatter = logging.Formatter('%(asctime)s %(process)s %(levelname)s: %(message)s')
    fileHandler = logging.FileHandler("./image_grabber/imgrabber.log", mode='a')
    fileHandler.setFormatter(formatter)
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(formatter)

    l = logging.getLogger(__name__)
    l.setLevel(logging.DEBUG)
    l.addHandler(fileHandler)
    l.addHandler(streamHandler)

    if RESUME:
        folders = next(os.walk(IMAGES_ROOT_PATH))[1]
        folders_int = [int(x) for x in folders]
        folders_int.sort()
        last_folder = folders_int[-1]
        print("Resuming from folder " + str(last_folder))
    else:
        print("Emptying directory...")
        shutil.rmtree(IMAGES_ROOT_PATH)

    for i in range(last_folder, NUM_FOLDERS):
        folder_path = IMAGES_ROOT_PATH + str(i)
        os.makedirs(folder_path, exist_ok=True)
        crawler.grabrdm(folder_path, IMAGES_PER_FOLDER, NUM_SEARCH_WORDS, zfill=5)
