from renderers import template_env


class GroupChatRankingRenderer(object):

    def __init__(self, rows):
        self.rows = rows

    def render(self):
        return template_env.get_template('group_chat_ranking.haml').render({'rows': self.rows})
