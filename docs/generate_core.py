def write_core_index(docs, tlobjects, layer):
    # Determine method, types and constructors count
    types = set()
    method_count = 0
    constructor_count = 0
    for tlobject in tlobjects:
        if tlobject.is_function:
            method_count += 1
        else:
            constructor_count += 1

        types.add(tlobject.result)

    type_count = len(types)
    types.clear()

    # Write the head and the full HTML
    docs.write_head('Telethon API', relative_css_path='css/docs.css')

    # Welcome text, small explanation about this page
    docs.write('''<h1>Telethon API</h1>
<p>This documentation was generated straight from the <code>scheme.tl</code>
provided by Telegram. However, there is no official documentation per se
on what the methods, constructors and types mean. Nevertheless, this
page aims to provide easy access to all the available methods, their
definition and parameters.</p>

<p>Although this documentation was generated for <i>Telethon</i>, it may
be useful for any other Telegram library out there.</p>'''

               # Methods section
               '''<h3 id="methods">Methods</h3>
<p>Currently there are <b>{methodcount} methods</b> available for the layer
{layer}. The complete list can be seen <a href="methods/index.html">here</a>.
<br />
To invoke any of these methods (also called <i>requests</i>), you can do
as shown on the following example:</p>'''

               # Example usage for the methods
               '''<pre><span class="sh3">#!/usr/bin/python3</span>
<span class="sh4">from</span> telethon <span class="sh4">import</span> TelegramClient
<span class="sh4">from</span> telethon.tl.functions.messages <span class="sh4">import</span> GetHistoryRequest
<span class="sh4">from</span> telethon.utils <span class="sh4">import</span> get_input_peer

<span class="sh3"># Use your own values here</span>
api_id = <span class="sh1">12345</span>
api_hash = <span class="sh2">'0123456789abcdef0123456789abcdef'</span>
phone_number = <span class="sh2">'+34600000000'</span>

<span class="sh3"># Create the client and connect</span>
client = TelegramClient(<span class="sh2">'username'</span>, api_id, api_hash)
client.connect()

<span class="sh3"># Ensure you're authorized</span>
if not client.is_user_authorized():
    client.send_code_request(phone)
    client.sign_in(phone, input(<span class="sh2">'Enter the code: '</span>))

<span class="sh3"># Using built-in methods</span>
dialogs, entities = client.get_dialogs(<span class="sh1">10</span>)
entity = entities[<span class="sh1">0</span>]

<span class="sh3"># !! Invoking a request manually !!</span>
result = <b>client.invoke</b>(
    GetHistoryRequest(
        get_input_peer(entity),
        limit=<span class="sh1">20</span>,
        offset_date=<span class="sh1">None</span>,
        offset_id=<span class="sh1">0</span>,
        max_id=<span class="sh1">0</span>,
        min_id=<span class="sh1">0</span>,
        add_offset=<span class="sh1">0</span>))

<span class="sh3"># Now you have access to the first 20 messages</span>
messages = result.messages</pre>'''

               # Example end
               '''<p>As you can see, manually invoking requests with <code>client.invoke()</code>
is way more verbose than using the built-in methods. However, and given
that there are so many methods available, it's impossible to provide a nice
interface to things that may change over time. To get full access, however,
you're still able to invoke these methods manually.</p>'''

               # Types section
               '''<h3 id="types">Types</h3>
<p>Currently there are <b>{typecount} types</b>. You can see the full
list <a href="types/index.html">here</a>.</p>

<p>The Telegram types are the <i>abstract</i> results that you receive
after invoking a request. They are "abstract" because they can have
multiple constructors. For instance, the abstract type <code>User</code>
can be either <code>UserEmpty</code> or <code>User</code>. You should,
most of the time, make sure you received the desired type by using
the <code>isinstance(result, Constructor)</code> Python function.

When a request needs a Telegram type as argument, you should create
an instance of it by using one of its, possibly multiple, constructors.</p>'''

               # Constructors section
               '''<h3 id="constructors">Constructors</h3>
<p>Currently there are <b>{constructorcount} constructors</b>. You can see
the full list <a href="constructors/index.html">here</a>.</p>

<p>Constructors are the way you can create instances of the abstract types
described above, and also the instances which are actually returned from
the functions although they all share a common abstract type.</p>'''

               # Core types section
               '''<h3 id="core">Core types</h3>
<p>Core types are types from which the rest of Telegram types build upon:</p>
<ul>
<li id="int"><b>int</b>:
    The value should be an integer type, like <span class="sh1">42</span>.
    It should have 32 bits or less. You can check the bit length by
    calling <code>a.bit_length()</code>, where <code>a</code> is an
    integer variable.
</li>
<li id="long"><b>long</b>:
    Different name for an integer type. The numbers given should have
    64 bits or less.
</li>
<li id="int128"><b>int128</b>:
    Another integer type, should have 128 bits or less.
</li>
<li id="int256"><b>int256</b>:
    The largest integer type, allowing 256 bits or less.
</li>

<li id="double"><b>double</b>:
    The value should be a floating point value, such as
    <span class="sh1">123.456</span>.
</li>

<li id="vector"><b>Vector&lt;T&gt;</b>:
    If a type <code>T</code> is wrapped around <code>Vector&lt;T&gt;</code>,
    then it means that the argument should be a <i>list</i> of it.
    For instance, a valid value for <code>Vector&lt;int&gt;</code>
    would be <code>[1, 2, 3]</code>.
</li>

<li id="string"><b>string</b>:
    A valid UTF-8 string should be supplied. This is right how
    Python strings work, no further encoding is required.
</li>

<li id="bool"><b>Bool</b>:
    Either <code>True</code> or <code>False</code>.
</li>

<li id="true"><b>true</b>:
    These arguments aren't actually sent but rather encoded as flags.
    Any truthy value (<code>True</code>, <code>7</code>) will enable
    this flag, although it's recommended to use <code>True</code> or
    <code>None</code> to symbolize that it's not present.
</li>

<li id="bytes"><b>bytes</b>:
    A sequence of bytes, like <code>b'hello'</code>, should be supplied.
</li>

<li id="date"><b>date</b>:
    Although this type is internally used as an <code>int</code>,
    you can pass a <code>datetime</code> object instead to work
    with date parameters.
</li>
</ul>'''.format(
        layer=layer,
        typecount=type_count,
        methodcount=method_count,
        constructorcount=constructor_count
    ))
    docs.end_body()
