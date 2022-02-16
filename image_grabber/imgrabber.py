import random
import requests
import pathlib
import re
import imghdr
import logging
import urllib.parse, urllib.error
from requests.api import head

GOOGLE_SEARCH_BASE_URL = "https://www.google.com/search"
URL_REGEX_PATTERN = ('\["(?:https:|http[^"]*?)", *\d+, *\d+\],'
                     ' *\["(https:|http[^"]*?)", *\d+, *\d+\]')
URL_SEARCH_WORDS_KEY_ANY = "as_oq"
URL_SEARCH_WORDS_KEY_ALL = "as_q"
DEFAULT_HEADERS = {
    "User-Agent":
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
     "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15"),
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

    def __init__(self,
                 words=None,
                 headers=DEFAULT_HEADERS,
                 payload=DEFAULT_PAYLOAD) -> None:
        """Construct an ImGrabber instance for searching and downloading images
        from Google Images

        Args:
            words (list, optional): List of string words to use for image
                                    search
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
        """Perform an image search and get the links to the first 100 photos in
        the search

        Args:
            words (list, optional): List of string words to use for image
                                    search. If None, uses instance's words list
            type (str, optional): Type of search to use for words. Can be 'any'
                                  or 'all'. 'all' implies OR between each
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
            raise ValueError("Type argument must be 'any' or 'all'. Got " +
                             str(type))

        payload_str = urllib.parse.urlencode(payload, safe=':,')
        r = requests.get(
            GOOGLE_SEARCH_BASE_URL, params=payload_str, headers=self.headers)
        self.search_url = r.url
        self.links = re.findall(URL_REGEX_PATTERN, str(r.text))

        return self.links.copy()

    def searchrdm(self, k, words=None, type='all'):
        """Perform an image search using a random selection of words. Selects k
        random words from words or self.words

        Args:
            k (int): number of words to select
            words (list, optional): list of words to choose from. If
                                    words==None, uses self.words
            type (str, optional): Type of search to use for words. Can be 'any'
                                  or 'all'. 'all' implies OR between each
                                  keyword search
        """
        if words is None:
            words = self.words

        search_words = random.choices(words, k=k)
        self.search(words=search_words, type=type)

        return search_words

    def download(self,
                 destination,
                 links=None,
                 prefix='',
                 suffix='',
                 start=0,
                 zfill=0,
                 maximgs=100):
        """Download images to destination

        Args:
            destination (str): folderpath to download to
            links (list, optional): list of links to images to download.
                                    Defaults to None.
            prefix (str, optional): image file prefix. Defaults to ''.
            suffix (str, optional): image file suffix. Defaults to ''.
            start (int, optional): number to start file numbering with.
                                   Defaults to 0.
            zfill (int, optional): number of zeros to fill image filename with.
                                   Defaults to 0.
            maximgs (int, optional): max number of images to download. Defaults
                                     to 100.

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
                img_path = pathlib.Path(destination) / img_name

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
                        img_path = img_path.rename(
                            img_path.with_suffix('.' + img_type))
                        self.logger.debug("Saved " + str(img_path))
                        i += 1
                    else:
                        self.logger.warning(
                            "Not a known image type (from {}\) skipping...".
                            format(link))
                        img_path.unlink()

                else:  # Got an error
                    self.logger.error("Got: HTTP Error " + str(r.status_code) +
                                      " from link " + link)

            except Exception as err:
                self.logger.exception(err)

            if i == maximgs:
                break

        return i

    def grabrdm(self,
                destination,
                n,
                k,
                type='all',
                links=None,
                prefix='',
                suffix='',
                zfill=0,
                n_infolder=0):

        while n_infolder < n:
            search_words = self.searchrdm(k, type=type)
            words_str = ' '.join(
                search_words) if type == 'all' else ' OR '.join(search_words)
            self.logger.info("Search: " + words_str)
            n_infolder += self.download(
                destination,
                links=links,
                prefix=prefix,
                suffix=suffix,
                start=n_infolder,
                zfill=zfill,
                maximgs=(n - n_infolder))

if __name__ == "__main__":
    import shutil

    NOUNS_PATH = pathlib.Path("./image_grabber/nounlist.txt")
    IMAGES_ROOT_PATH = pathlib.Path("./image_grabber/images/")
    NUM_SEARCH_WORDS  = 3
    NUM_FOLDERS       = 3
    IMAGES_PER_FOLDER = 10
    RESUME            = True

    with open(NOUNS_PATH) as words_file:
        words = [word.strip() for word in words_file.readlines()]

    crawler = ImGrabber(words)
    formatter = logging.Formatter(
        '%(asctime)s %(process)s %(levelname)s: %(message)s')
    fileHandler = logging.FileHandler(
        "./image_grabber/imgrabber.log", mode='a')
    fileHandler.setFormatter(formatter)
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(formatter)

    l = logging.getLogger(__name__)
    l.setLevel(logging.DEBUG)
    l.addHandler(fileHandler)
    l.addHandler(streamHandler)

    if RESUME and IMAGES_ROOT_PATH.exists():
        # TODO: This should be refactored. The main goal here is to find the
        # the latest folder, then find the latest image, remove the most recent
        # image, and start the search by re-downloading the just removed image.
        # Right now, it will fail if the filenames don't have leading 0s and
        # probably in other cases too.
        folders = [d.stem for d in IMAGES_ROOT_PATH.iterdir() if d.is_dir()]
        folders_int = [int(x) for x in folders]
        folders_int.sort()
        last_folder = folders_int[-1]
        images_path = pathlib.Path(IMAGES_ROOT_PATH / str(last_folder))
        images = [im.name for im in images_path.iterdir() if not im.is_dir()]
        images.sort()
        last_image = images[-1]
        print(IMAGES_ROOT_PATH)
        (IMAGES_ROOT_PATH / str(last_folder) / str(last_image)).unlink()
        print("Resuming from folder " + str(last_folder) +
              " picture " + str(last_image))
        last_image = int(pathlib.Path(last_image).stem)
    else:
        if IMAGES_ROOT_PATH.exists() and IMAGES_ROOT_PATH.is_dir():
            print("Emptying directory...")
            shutil.rmtree(IMAGES_ROOT_PATH)
        last_folder = 0
        last_image = 0

    print(last_image)
    for i in range(last_folder, NUM_FOLDERS):
        folder_path = IMAGES_ROOT_PATH / str(i)
        folder_path.mkdir(parents=True, exist_ok=True)
        crawler.grabrdm(
            folder_path,
            IMAGES_PER_FOLDER,
            NUM_SEARCH_WORDS,
            zfill=5,
            n_infolder=last_image)
