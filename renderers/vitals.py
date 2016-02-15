from renderers import template_env


class VitalsRenderer(object):

    def __init__(self, title, header_row, rows, subtitle=''):
        self.title = title
        self.subtitle = subtitle
        self.header_row = header_row
        self.rows = rows

    def render(self):
        return template_env.get_template('vitals.haml').render({
            'title': self.title,
            'subtitle': self.subtitle,
            'header_row': self.header_row,
            'rows': self.rows
        })
