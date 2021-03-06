import codecs
import datetime
import json
import sys
from collections import defaultdict
from dateutil.relativedelta import relativedelta

import shortcuts
import utils
from renderers import HighchartRenderer, TableRenderer, VitalsRenderer
from wxparser import Parser, UserData, Message


contrasty_colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33', '#a65628', '#f781bf', '#999999']
contrasty_colors_rgba = [
    'rgba(228, 26, 28, 0.6)',
    'rgba(55, 126, 184, 0.6)',
    'rgba(77, 175, 74, 0.6)',
    'rgba(152, 78, 163, 0.6)',
    'rgba(255, 127, 0, 0.6)',
    'rgba(255, 255, 51, 0.6)',
    'rgba(166, 86, 40, 0.6)',
    'rgba(247, 129, 191, 0.6)',
    'rgba(153, 153, 153, 0.6)'
]


class NullCategory(object):
    slug = 'other'


def build_sent_by_category_by_month_graph(wxp, userdata):
    # Build the timespans
    timespans = []
    rolling_date = datetime.datetime(2015, 1, 1, 0, 0, 0, 0, shortcuts.BEIJING_TIME)
    while rolling_date < shortcuts.BEGINNING_OF_2016:
        next_start = rolling_date + relativedelta(months=1)
        timespans.append((rolling_date, next_start))
        rolling_date = next_start

    raw_data = defaultdict(lambda: [0] * len(timespans))
    for thread in wxp.individual_threads:
        category_slug = thread.category.slug if getattr(thread, 'category', None) else 'other'
        for i in xrange(0, len(timespans)):
            from_timestamp, to_timestamp = timespans[i]
            raw_data[category_slug][i] += len(filter(lambda message: message.sent and message.timestamp >= from_timestamp and message.timestamp < to_timestamp, thread.messages))

    for thread in wxp.group_threads:
        for i in xrange(0, len(timespans)):
            from_timestamp, to_timestamp = timespans[i]
            raw_data['group-chats'][i] += len(filter(lambda message: message.sent and message.timestamp >= from_timestamp and message.timestamp < to_timestamp, thread.messages))

    sorted_keys = list(reversed(sorted(raw_data.keys(), key=lambda slug: sum(raw_data[slug]))))

    series_data = []
    for series in filter(lambda key: key not in ['other', 'group-chats'], sorted_keys):
        series_data.append({
            'name': userdata.categories[series].display_name,
            'data': raw_data[series],
        })

    series_data.append({
        'name': 'Group Chats',
        'data': raw_data['group-chats'],
    })

    series_data.append({
        'name': 'Other',
        'data': raw_data['other'],
    })

    return HighchartRenderer({
        'chart': {
            'type': 'column'
        },
        'title': {
            'text': 'Messages Sent (2015)'
        },
        'subtitle': {
            'text': 'by month, by category'
        },
        'colors': ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33', '#a65628', '#f781bf', '#999999'],
        'xAxis': {
            'categories': [timespan[0].strftime('%Y-%m') for timespan in timespans],
            'tickmarkPlacement': 'on',
            'title': {
                'enabled': False,
            },
        },
        'yAxis': {
            'title': {
                'text': 'Messages sent'
            },
        },
        'tooltip': {
            'shared': True,
            'valueSuffix': ' messages'
        },
        'plotOptions': {
            'column': {
                'stacking': 'normal',
                'lineWidth': 1,
            }
        },
        'series': series_data,
    })


class ScatterPlotSeries(object):

    def __init__(self, name, thread_filter, message_filter, color):
        self.name = name
        self.thread_filter = thread_filter
        self.message_filter = message_filter
        self.color = color


def build_message_scatterplot(wxp, title, series_list):

    def _day_of_year(timestamp):
        return int((timestamp - shortcuts.BEGINNING_OF_2015).total_seconds() / (60 * 60 * 24))

    def _hour_of_day(timestamp):
        return round(timestamp.hour + (timestamp.minute / 60.0), 2)

    series_output = []
    for series in series_list:
        # Start with the blank structure
        series_output.append({
            'name': series.name,
            'color': series.color,
            'data': [],
        })
        for thread in filter(series.thread_filter, wxp.threads):
            for message in filter(series.message_filter, filter(lambda message: message.timestamp >= shortcuts.BEGINNING_OF_2015 and message.timestamp < shortcuts.BEGINNING_OF_2016, thread.messages)):
                series_output[-1]['data'].append([_day_of_year(message.timestamp.astimezone(shortcuts.BEIJING_TIME)), _hour_of_day(message.timestamp.astimezone(shortcuts.BEIJING_TIME))])

    return HighchartRenderer({
        'chart': {
            'type': 'scatter',
            'zoomType': 'xy',
        },
        'title': {
            'text': title,
        },
        'xAxis': {
            'title': {
                'enabled': True,
                'text': 'Day of Year',
            },
            'tickPositions': [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365],
            # 'startOnTick': True,
            # 'endOnTick': True,
            # 'showLastLabel': True,
        },
        'yAxis': {
            'title': {
                'text': 'Hour of Day (China Standard Time)',
            },
            'min': 0,
            'max': 24,
            'tickPositions': [0, 4, 8, 12, 16, 20, 24],
        },
        'plotOptions': {
            'scatter': {
                'marker': {
                    'radius': 3,
                },
            },
        },
        'series': series_output,
    })


def build_sent_message_by_category_scatterplot(wxp, userdata):

    def _individual_thread_filter_generator(slug):
        return lambda thread: not thread.is_group_chat and getattr(thread, 'category', NullCategory()).slug == slug

    category_sums = defaultdict(lambda: 0)
    for thread in wxp.individual_threads:
        if getattr(thread, 'category', NullCategory()).slug == 'other':
            continue
        category_sums[thread.category.slug] += len(shortcuts.SENT_MESSAGES_IN_2015(thread))

    i = 0
    series_list = []
    for category in reversed(sorted(category_sums.keys(), key=lambda key: category_sums[key])):
        series_list.append(ScatterPlotSeries(userdata.categories[category].display_name,
                                             _individual_thread_filter_generator(category),
                                             lambda message: message.sent,
                                             contrasty_colors_rgba[i]))
        i += 1

    series_list.append(ScatterPlotSeries('Group Chats',
                                         lambda thread: thread.is_group_chat,
                                         lambda message: message.sent,
                                         contrasty_colors_rgba[i]))
    i += 1

    series_list.append(ScatterPlotSeries('Other',
                                         _individual_thread_filter_generator('other'),
                                         lambda message: message.sent,
                                         contrasty_colors_rgba[i]))
    i += 1

    return build_message_scatterplot(wxp, 'All Sent Messages (2015)', series_list)


def _group_chat_alias(original_display_name):
        try:
            return json.loads(open('group_chat_aliases.json', 'r').read()).get(original_display_name, original_display_name)
        except (IOError, ValueError):
            return original_display_name


def build_group_chat_ranking_table(wxp):
    group_chat_ranking = []
    for thread in list(reversed(sorted(wxp.group_threads, key=lambda thread: len(shortcuts.SENT_MESSAGES_IN_2015(thread))))):
        display_name = _group_chat_alias(thread.contact.display_name)
        if not display_name:
            continue
        my_sent = len(shortcuts.SENT_MESSAGES_IN_2015(thread))
        total_sent = len(shortcuts.MESSAGES_IN_2015(thread))
        percent = round(100.0 * my_sent / total_sent, 1)
        group_chat_ranking.append((display_name, _int_with_comma(my_sent), _int_with_comma(total_sent), percent))
        if len(group_chat_ranking) == 8:
            break

    return TableRenderer('Top Group Chats (2015)',
                         ['', 'Your<br/>messages', 'Total<br/>messages', '%'],
                         group_chat_ranking,
                         subtitle='By your messages sent')


def build_silent_group_chat_ranking_table(wxp):
    group_chat_ranking = []
    for thread in reversed(sorted(filter(lambda thread: len(shortcuts.SENT_MESSAGES_IN_2015(thread)) == 0, wxp.group_threads), key=lambda thread: len(shortcuts.MESSAGES_IN_2015(thread)))):
        display_name = _group_chat_alias(thread.contact.display_name)
        if not display_name:
            continue
        my_sent = len(shortcuts.SENT_MESSAGES_IN_2015(thread))
        total_sent = len(shortcuts.MESSAGES_IN_2015(thread))
        percent = round(100.0 * my_sent / total_sent, 1)
        group_chat_ranking.append((display_name, _int_with_comma(my_sent), _int_with_comma(total_sent), percent))
        if len(group_chat_ranking) == 8:
            break

    return TableRenderer('Peak Lurk (2015)',
                         ['', 'Your<br/>messages', 'Total<br/>messages', '%'],
                         group_chat_ranking,
                         subtitle='Busiest Groups Where You Said Nothing All Year')


def build_individual_chat_ranking_table(wxp):
    ranking = []
    total_sent_messages = sum([len(shortcuts.SENT_MESSAGES_IN_2015(thread)) for thread in wxp.threads])
    for thread in list(reversed(sorted(wxp.individual_threads, key=lambda thread: len(shortcuts.SENT_MESSAGES_IN_2015(thread)))))[:10]:
        display_name = thread.contact.display_name
        my_sent = len(shortcuts.SENT_MESSAGES_IN_2015(thread))
        total = len(shortcuts.MESSAGES_IN_2015(thread))
        percent = round(100.0 * len(shortcuts.SENT_MESSAGES_IN_2015(thread)) / total_sent_messages, 1)
        ranking.append((display_name, _int_with_comma(my_sent), percent, _int_with_comma(total)))
        if len(ranking) == 10:
            break

    top_five_percent = sum(x[2] for x in ranking[:5])

    return TableRenderer('Top Contacts (2015)',
                         ['', 'Your<br/>messages', '% of all 2015<br/>sent messages', 'Total<br/>messages'],
                         ranking,
                         subtitle='%.1f%% of your sent messages were to just five people' % top_five_percent)


def build_sent_by_time_heatmap(wxp):
    time_dict = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    for thread in wxp.threads:
        for message in shortcuts.SENT_MESSAGES_IN_2015(thread):
            weekday = message.timestamp.astimezone(shortcuts.BEIJING_TIME).weekday()
            hour_bucket = (message.timestamp.astimezone(shortcuts.BEIJING_TIME).hour / 4)
            time_dict[weekday][hour_bucket] += 1

    weekdays_in_year_divisor = defaultdict(lambda: 0)
    rolling_date = shortcuts.BEGINNING_OF_2015
    while rolling_date < shortcuts.BEGINNING_OF_2016:
        weekdays_in_year_divisor[rolling_date.weekday()] += 1
        rolling_date += datetime.timedelta(days=1)

    series_splayed = []
    for weekday in xrange(0, 7):
        for hour_bucket in xrange(0, 6):
            series_splayed.append([weekday, hour_bucket, time_dict[weekday][hour_bucket] / weekdays_in_year_divisor[weekday]])

    return HighchartRenderer({
        'chart': {
            'type': 'heatmap',
            'marginTop': 40,
            'marginBottom': 80,
            'plotBorderWidth': 1,
        },
        'title': {
            'text': 'Sent message average (2015)',
        },
        'xAxis': {
            'categories': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        },
        'yAxis': {
            'categories': ['0:00-3:59', '4:00-7:59', '8:00-11:59', '12:00-15:59', '16:00-19:59', '20:00-23:59'],
            'title': None,
        },
        'colorAxis': {
            'min': 0,
            'minColor': '#000000',
            'maxColor': contrasty_colors[2],
        },
        'legend': {
            'align': 'right',
            'layout': 'vertical',
            'margin': 0,
            'verticalAlign': 'top',
            'y': 25,
            'symbolHeight': 280,
        },
        'series': [{
            'name': 'Average messages per day',
            'borderWidth': 1,
            'data': series_splayed,
            'dataLabels': {
                'enabled': True,
                'color': '#ffffff'
            },
        }],
    })


def build_sent_by_category_heatmap(wxp, userdata):
    category_dict = defaultdict(lambda: defaultdict(lambda: 0))
    seen_categories = set([])
    for thread in wxp.individual_threads:
        category_slug = getattr(thread, 'category', NullCategory()).slug
        if category_slug == 'other':
            continue
        seen_categories.add(category_slug)
        for message in shortcuts.SENT_MESSAGES_IN_2015(thread):
            weekday = message.timestamp.astimezone(shortcuts.BEIJING_TIME).weekday()
            category_dict[weekday][category_slug] += 1

    weekdays_in_year_divisor = defaultdict(lambda: 0)
    rolling_date = shortcuts.BEGINNING_OF_2015
    while rolling_date < shortcuts.BEGINNING_OF_2016:
        weekdays_in_year_divisor[rolling_date.weekday()] += 1
        rolling_date += datetime.timedelta(days=1)

    series_splayed = []
    for weekday in xrange(0, 7):
        for i, category_slug in enumerate(sorted(seen_categories)):
            series_splayed.append([weekday, i, category_dict[weekday][category_slug] / weekdays_in_year_divisor[weekday]])

    return HighchartRenderer({
        'chart': {
            'type': 'heatmap',
            'marginTop': 40,
            'marginBottom': 80,
            'plotBorderWidth': 1,
        },
        'title': {
            'text': 'Sent message average (2015)',
        },
        'xAxis': {
            'categories': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        },
        'yAxis': {
            'categories': [userdata.categories[category_slug].display_name for category_slug in sorted(seen_categories)],
            'title': None,
        },
        'colorAxis': {
            'min': 0,
            'minColor': '#000000',
            'maxColor': contrasty_colors[2],
        },
        'legend': {
            'align': 'right',
            'layout': 'vertical',
            'margin': 0,
            'verticalAlign': 'top',
            'y': 25,
            'symbolHeight': 280,
        },
        'series': [{
            'name': 'Average messages per day',
            'borderWidth': 1,
            'data': series_splayed,
            'dataLabels': {
                'enabled': True,
                'color': '#ffffff'
            },
        }],
    })


def build_scalars_table(wxp):
    individual_sent_messages = sum([len(shortcuts.SENT_MESSAGES_IN_2015(thread)) for thread in wxp.individual_threads])
    group_sent_messages = sum([len(shortcuts.SENT_MESSAGES_IN_2015(thread)) for thread in wxp.group_threads])
    total_sent_messages = individual_sent_messages + group_sent_messages

    individual_received_messages = sum([len(filter(lambda message: not message.sent, shortcuts.MESSAGES_IN_2015(thread))) for thread in wxp.individual_threads])
    group_received_messages = sum([len(filter(lambda message: not message.sent, shortcuts.MESSAGES_IN_2015(thread))) for thread in wxp.group_threads])

    blank_row = ['' * 3]

    individual_chat_count = len(filter(lambda thread: len(shortcuts.MESSAGES_IN_2015(thread)) > 0, wxp.individual_threads))
    group_chat_count = len(filter(lambda thread: len(shortcuts.MESSAGES_IN_2015(thread)) > 0, wxp.group_threads))

    sent_sticker_count = sum([len(filter(lambda message: message.type == Message.TYPE_STICKER, shortcuts.SENT_MESSAGES_IN_2015(thread))) for thread in wxp.threads])
    received_sticker_count = sum([len(filter(lambda message: not message.sent and message.type == Message.TYPE_STICKER, shortcuts.MESSAGES_IN_2015(thread))) for thread in wxp.threads])

    sent_hongbao_count = sum([len(filter(lambda message: message.type in [Message.TYPE_HONGBAO, Message.TYPE_TRANSFER], shortcuts.SENT_MESSAGES_IN_2015(thread))) for thread in wxp.threads])
    received_hongbao_count = sum([len(filter(lambda message: not message.sent and message.type in [Message.TYPE_HONGBAO, Message.TYPE_TRANSFER], shortcuts.MESSAGES_IN_2015(thread))) for thread in wxp.individual_threads])

    rows = [
        ['In 2015, you sent', _int_with_comma(total_sent_messages), 'messages'],
        ['', _int_with_comma(individual_sent_messages), 'were to individuals,'],
        ['and', _int_with_comma(group_sent_messages), 'were to groups'],
        blank_row,
        blank_row,
        ['You received', _int_with_comma(individual_received_messages + group_received_messages), 'messages'],
        ['', _int_with_comma(individual_received_messages), 'from individuals'],
        ['and', _int_with_comma(group_received_messages), 'via groups'],
        blank_row,
        blank_row,
        ['You talked to', individual_chat_count, 'people via individual chat'],
        ['and were in', group_chat_count, 'active group chats'],
        blank_row,
        blank_row,
        ['You sent', _int_with_comma(sent_sticker_count), 'stickers'],
        ['and received', _int_with_comma(received_sticker_count), ''],
        blank_row,
        blank_row,
        ['You sent', _int_with_comma(sent_hongbao_count), u'\u7ea2\u5305 / \u8f6c\u8d26'],
        ['and received', _int_with_comma(received_hongbao_count), '(excluding groups)'],
    ]

    return VitalsRenderer('Vitals (2015)',
                          blank_row,
                          rows)


def _int_with_comma(integer):
    return '{:,d}'.format(integer)


if __name__ == '__main__':
    parser = utils.argparser_with_generic_arguments('Do all the things.')
    args = parser.parse_args()
    wxp = Parser(args.db_file_path)
    userdata = UserData.initialize(wxp)

    if len(userdata.categories) == 0:
        print
        print 'You have not yet added any categorizations for threads.'
        print 'This will result in missing or suboptimal output.'
        print
        print 'You should run `python categorize.py` to categorize, before you run this script.'
        print
        sys.exit(1)

    renderers = [
        lambda: build_sent_by_category_by_month_graph(wxp, userdata),
        lambda: build_sent_message_by_category_scatterplot(wxp, userdata),
        lambda: build_individual_chat_ranking_table(wxp),
        lambda: build_group_chat_ranking_table(wxp),
        lambda: build_silent_group_chat_ranking_table(wxp),
        lambda: build_sent_by_time_heatmap(wxp),
        lambda: build_sent_by_category_heatmap(wxp, userdata),
        lambda: build_scalars_table(wxp),
    ]

    for i in xrange(0, len(renderers)):
        print 'Building renderer %d...' % i
        renderer = renderers[i]()
        print 'Rendering output...'
        chart_file = codecs.open('chart%d.html' % i, 'w', encoding='utf-8')
        chart_file.write(renderer.render())
        chart_file.close()
