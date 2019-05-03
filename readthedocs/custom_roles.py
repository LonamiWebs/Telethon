from docutils import nodes, utils
from docutils.parsers.rst.roles import set_classes


def make_link_node(rawtext, app, name, options):
    """
    Create a link to the TL reference.

    :param rawtext: Text being replaced with link node.
    :param app: Sphinx application context
    :param name: Name of the object to link to
    :param options: Options dictionary passed to role func.
    """
    try:
        base = app.config.tl_ref_url
        if not base:
            raise AttributeError
    except AttributeError as e:
        raise ValueError('tl_ref_url config value is not set') from e

    if base[-1] != '/':
        base += '/'

    set_classes(options)
    node = nodes.reference(rawtext, utils.unescape(name),
                           refuri='{}?q={}'.format(base, name),
                           **options)
    return node


# noinspection PyUnusedLocal
def tl_role(name, rawtext, text, lineno, inliner, options=None, content=None):
    """
    Link to the TL reference.

    Returns 2 part tuple containing list of nodes to insert into the
    document and a list of system messages. Both are allowed to be empty.

    :param name: The role name used in the document.
    :param rawtext: The entire markup snippet, with role.
    :param text: The text marked with the role.
    :param lineno: The line number where rawtext appears in the input.
    :param inliner: The inliner instance that called us.
    :param options: Directive options for customization.
    :param content: The directive content for customization.
    """
    if options is None:
        options = {}

    # TODO Report error on type not found?
    # Usage:
    #   msg = inliner.reporter.error(..., line=lineno)
    #   return [inliner.problematic(rawtext, rawtext, msg)], [msg]
    app = inliner.document.settings.env.app
    node = make_link_node(rawtext, app, text, options)
    return [node], []


def setup(app):
    """
    Install the plugin.

    :param app: Sphinx application context.
    """
    app.add_role('tl', tl_role)
    app.add_config_value('tl_ref_url', None, 'env')
    return
