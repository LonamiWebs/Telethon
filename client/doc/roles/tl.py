# type: ignore
from docutils import nodes, utils
from docutils.parsers.rst.roles import set_classes


def make_link_node(rawtext, app, name, options):
    try:
        base = app.config.tl_ref_url
        if not base:
            raise AttributeError
    except AttributeError as e:
        raise ValueError("tl_ref_url config value is not set") from e

    if base[-1] != "/":
        base += "/"

    set_classes(options)
    node = nodes.reference(
        rawtext, utils.unescape(name), refuri="{}?q={}".format(base, name), **options
    )
    return node


def tl_role(name, rawtext, text, lineno, inliner, options=None, content=None):
    if options is None:
        options = {}

    app = inliner.document.settings.env.app
    node = make_link_node(rawtext, app, text, options)
    return [node], []


def setup(app):
    app.add_role("tl", tl_role)
    app.add_config_value("tl_ref_url", None, "env")
