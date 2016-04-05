import argparse
import re
import unicodedata


def argparser_with_generic_arguments(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('db_file_path',
                        metavar='DECRYPTED_DATABASE_FILE',
                        type=str,
                        help='path to the decrypted SQLite database you want to use')
    return parser


def slugify(value):
    value = unicodedata.normalize('NFKD', unicode(value)).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)
