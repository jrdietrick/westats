import os
import jinja2
from hamlish_jinja import HamlishExtension

template_loader = jinja2.FileSystemLoader(searchpath=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'))
template_env = jinja2.Environment(loader=template_loader, extensions=[HamlishExtension])
template_env.hamlish_mode = 'indented'
template_env.hamlish_enable_div_shortcut = True

from renderers.highchart import HighchartRenderer
from renderers.table import TableRenderer
from renderers.vitals import VitalsRenderer
