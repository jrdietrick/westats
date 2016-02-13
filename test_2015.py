import datetime
import re

from collections import defaultdict
from wxparser import Parser, UserData, Category, _slugify


class CST(datetime.tzinfo):

    def utcoffset(self, dt):
        return datetime.timedelta(hours=8)

    def tzname(self, dt):
        return 'China Standard Time'

    def dst(self, dt):
        return datetime.timedelta(hours=8)


beijing_time = CST()


if __name__ == '__main__':
    wxp = Parser('decrypted.db')
    userdata = UserData.initialize(wxp)

    beginning_of_2015 = datetime.datetime(2015, 2, 19, 0, 0, 0, 0, beijing_time)
    beginning_of_2016 = datetime.datetime(2016, 2, 8, 0, 0, 0, 0, beijing_time)

    def _chats_in_2015(thread):
        return thread.message_count_between(beginning_of_2015, beginning_of_2016)

    def _sent_chats_in_2015(thread):
        return thread.message_sent_count_between(beginning_of_2015, beginning_of_2016)

    total_individual_chats = sum([_chats_in_2015(thread) for thread in wxp.individual_threads])
    individual_sent_messages = sum([thread.message_sent_count_between(beginning_of_2015, beginning_of_2016) for thread in wxp.individual_threads])
    group_sent_messages = sum([thread.message_sent_count_between(beginning_of_2015, beginning_of_2016) for thread in wxp.group_threads])
    total_sent_messages = individual_sent_messages + group_sent_messages

    # Figure out how many people we need
    # to categorize to get to 90% of chats
    cumulative = 0
    to_categorize = []
    for thread in list(reversed(sorted(wxp.individual_threads, key=lambda thread: _chats_in_2015(thread)))):
        cumulative += _chats_in_2015(thread)
        to_categorize.append(thread)
        if float(cumulative) / total_individual_chats > 0.90:
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

        if _slugify(user_entry) in userdata.categories.keys():
            # Matches an existing category by slug
            userdata.categories[_slugify(user_entry)].add_thread(thread)
            userdata.save()
            continue

        # Whole new category
        new_category = Category(user_entry)
        userdata.add_category(new_category)
        new_category.add_thread(thread)
        userdata.save()

    by_category = defaultdict(lambda: 0)
    for thread in wxp.individual_threads:
        category_slug = thread.category.slug if getattr(thread, 'category', None) else 'other'
        by_category[category_slug] += _chats_in_2015(thread)

    print
    print 'TOTAL'
    for category in list(reversed(sorted(by_category, key=lambda x: by_category[x]))):
        display_name = 'Other' if category == 'other' else userdata.categories[category].display_name
        print display_name, '%.1f%%' % (float(by_category[category]) / float(total_individual_chats) * 100.0)

    sent_by_category = defaultdict(lambda: 0)
    for thread in wxp.individual_threads:
        category_slug = thread.category.slug if getattr(thread, 'category', None) else 'other'
        sent_by_category[category_slug] += _sent_chats_in_2015(thread)

    print
    print 'SENT'
    for category in list(reversed(sorted(sent_by_category, key=lambda x: sent_by_category[x]))):
        display_name = 'Other' if category == 'other' else userdata.categories[category].display_name
        print display_name, '%.1f%%' % (float(sent_by_category[category]) / float(individual_sent_messages) * 100.0)

    print
    cumulative = 0
    people = 0
    for thread in list(reversed(sorted(wxp.individual_threads, key=lambda thread: _chats_in_2015(thread)))):
        cumulative += _chats_in_2015(thread)
        people += 1
        if people in [1, 3, 5, 10, 20]:
            print '%.1f%% of chatting is with only %d people' % (float(cumulative) / float(total_individual_chats) * 100.0, people)

    print
    print '%.1f%% of your sent messages go to groups' % (float(group_sent_messages) / float(total_sent_messages) * 100)
    print '%.1f%% of your sent messages go to individuals' % (float(individual_sent_messages) / float(total_sent_messages) * 100)
