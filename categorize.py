import re

import shortcuts
import utils
from wxparser import Parser, UserData, Category


class FuzzyRange(object):

    def __init__(self, start, end):
        self.start = start
        self.end = end

    def __eq__(self, other):
        return self.start <= other <= self.end


def parse_arguments(generic_parser):
    generic_parser.add_argument('threshold',
                                metavar='THRESHOLD',
                                type=float,
                                nargs='?',
                                choices=[FuzzyRange(0.0, 1.0)],
                                default=0.85,
                                help='threshold for portion of threads to categorize; \
                                      threads are ordered from most to least popular, by your sent messages; \
                                      must be between 0.0 and 1.0 (default 0.85)')
    return generic_parser.parse_args()


if __name__ == '__main__':
    parser = utils.argparser_with_generic_arguments('Simple tool to help you categorize threads.')
    args = parse_arguments(parser)
    wxp = Parser(args.db_file_path)
    userdata = UserData.initialize(wxp)

    total_individual_chats = sum([len(shortcuts.MESSAGES_IN_2015(thread)) for thread in wxp.individual_threads])
    individual_sent_messages = sum([len(shortcuts.SENT_MESSAGES_IN_2015(thread)) for thread in wxp.individual_threads])
    group_sent_messages = sum([len(shortcuts.SENT_MESSAGES_IN_2015(thread)) for thread in wxp.group_threads])
    total_sent_messages = individual_sent_messages + group_sent_messages

    # Figure out how many people we need
    # to categorize to get to the threshold
    total_cumulative = 0
    individual_cumulative = 0
    to_categorize = []
    for thread in list(reversed(sorted(wxp.threads, key=lambda thread: len(shortcuts.SENT_MESSAGES_IN_2015(thread))))):
        if not thread.is_group_chat:
            individual_cumulative += len(shortcuts.SENT_MESSAGES_IN_2015(thread))
        total_cumulative += len(shortcuts.SENT_MESSAGES_IN_2015(thread))
        to_categorize.append(thread)
        if float(total_cumulative) / total_sent_messages > args.threshold and float(individual_cumulative) / individual_sent_messages > args.threshold:
            break

    for thread in to_categorize:
        if getattr(thread, 'category', None):
            continue
        print thread.contact.display_name
        print
        categories_list = userdata.categories_as_list()
        for i in xrange(0, len(categories_list)):
            print '%4d - %s' % (i, categories_list[i].display_name)
        print

        user_entry = raw_input('Enter a number or name a new category: ').strip()
        if re.compile('\d+').match(user_entry):
            try:
                selected_category_index = int(user_entry)
                if selected_category_index >= 0 and selected_category_index < len(categories_list):
                    selected_category = categories_list[selected_category_index]
                    selected_category.add_thread(thread)
                    userdata.save()
                    continue
            except ValueError:
                pass

        if utils.slugify(user_entry) in userdata.categories.keys():
            # Matches an existing category by slug
            userdata.categories[utils.slugify(user_entry)].add_thread(thread)
            userdata.save()
            continue

        # Whole new category
        new_category = Category(user_entry)
        userdata.add_category(new_category)
        new_category.add_thread(thread)
        userdata.save()
