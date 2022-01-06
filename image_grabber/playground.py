import logging

logging.basicConfig(
    format='%(asctime)s %(process)s %(levelname)s: %(message)s',
    filename='example.log',
    level=logging.DEBUG)
logging.debug('This message should appear in the file')
logging.info('So should this')
logging.warning('And this, too')