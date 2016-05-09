from shortcuts import SENT_MESSAGES_IN_2015
from wxparser import Parser, Message
from wordcloud import WordCloud, STOPWORDS


wxp = Parser('decrypted.db')
# reddit_thread = wxp.get_group_chat_with_name('/r/beijing', True)
# gc = reddit_thread.group_chat
# ppm = gc.calculate_posts_per_member()
# ranking = list(reversed(sorted(gc.members.keys(), key=lambda member: ppm[member])))

contrasty_colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33', '#a65628', '#f781bf', '#999999']


from random import Random
from PIL import ImageColor
import colorsys


def get_single_color_func(color):
    """Create a color function which returns a single hue and saturation with.
    different values (HSV). Accepted values are color strings as usable by PIL/Pillow.

    >>> color_func1 = get_single_color_func('deepskyblue')
    >>> color_func2 = get_single_color_func('#00b4d2')
    """
    old_r, old_g, old_b = ImageColor.getrgb(color)
    rgb_max = 255.
    h, s, v = colorsys.rgb_to_hsv(old_r/rgb_max, old_g/rgb_max, old_b/rgb_max)

    def single_color_func(word=None, font_size=None, position=None,
                          orientation=None, font_path=None, random_state=None):
        """Random color generation.

        Additional coloring method. It picks a random value with hue and
        saturation based on the color given to the generating function.

        Parameters
        ----------
        word, font_size, position, orientation  : ignored.

        random_state : random.Random object or None, (default=None)
          If a random object is given, this is used for generating random numbers.

        """
        if random_state is None:
            random_state = Random()
        r, g, b = colorsys.hsv_to_rgb(h, s, random_state.uniform(0.7, 1))
        return 'rgb({:.0f}, {:.0f}, {:.0f})'.format(r * rgb_max, g * rgb_max, b * rgb_max)
    return single_color_func


if __name__ == '__main__':
    all_sent_text_messages_2015 = []
    for thread in wxp.threads:
        for message in SENT_MESSAGES_IN_2015(thread):
            if message.type == Message.TYPE_NORMAL:
                all_sent_text_messages_2015.append(message)

    raw_content = '\n'.join([message.content.lower() for message in all_sent_text_messages_2015])

    stopwords = STOPWORDS.copy()
    stopwords.add('int')
    stopwords.add('ext')
    stopwords.add('one')

    wc = WordCloud(stopwords=stopwords,
                   color_func=get_single_color_func(contrasty_colors[2]),
                   width=800,
                   height=800,
                   relative_scaling=1).generate(raw_content)
    filename = 'cloud.png'
    wc.to_file(filename)
