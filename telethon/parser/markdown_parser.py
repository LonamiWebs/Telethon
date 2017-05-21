from ..tl.types import (MessageEntityBold, MessageEntityCode,
                        MessageEntityItalic, MessageEntityTextUrl)


def parse_message_entities(msg):
    """Parses a message and returns the parsed message and the entities (bold, italic...).
       Note that although markdown-like syntax is used, this does not reflect the complete specification!"""

    # Store the entities here
    entities = []

    # Convert the message to a mutable list
    msg = list(msg)

    # First, let's handle all the text links in the message, so afterwards it's clean
    # for us to get our hands dirty with the other indicators (bold, italic and fixed)
    url_indices = [None] * 4  # start/end text index, start/end url index
    valid_url_indices = []  # all the valid url_indices found
    for i, c in enumerate(msg):
        if c is '[':
            url_indices[0] = i

        # From now on, also ensure that the last item was set
        elif c == ']' and url_indices[0]:
            url_indices[1] = i

        elif c == '(' and url_indices[1]:
            # If the previous index (']') is not exactly before the current index ('('),
            # then it's not a valid text link, so clear the previous state
            if url_indices[1] != i - 1:
                url_indices[:2] = [None] * 2
            else:
                url_indices[2] = i

        elif c == ')' and url_indices[2]:
            # We have succeeded to find a markdown-like text link!
            url_indices[3] = i
            valid_url_indices.append(url_indices[:])  # Append a copy
            url_indices = [None] * 4

    # Iterate in reverse order to clean the text from the urls
    # (not to affect previous indices) and append MessageEntityTextUrl's
    for i in range(len(valid_url_indices) - 1, -1, -1):
        vui = valid_url_indices[i]

        # Add 1 when slicing the message not to include the [] nor ()
        # There is no need to subtract 1 on the later part because that index is already excluded
        link_text = ''.join(msg[vui[0] + 1:vui[1]])
        link_url = ''.join(msg[vui[2] + 1:vui[3]])

        # After we have retrieved both the link text and url, replace them in the message
        # Now we do have to add 1 to include the [] and () when deleting and replacing!
        del msg[vui[2]:vui[3] + 1]
        msg[vui[0]:vui[1] + 1] = link_text

        # Finally, update the current valid index url to reflect that all the previous VUI's will be removed
        # This is because, after the previous VUI's get done, their part of the message is removed too,
        # hence we need to update the current VUI subtracting that removed part length
        for prev_vui in valid_url_indices[:i]:
            prev_vui_length = prev_vui[3] - prev_vui[2] - 1
            displacement = prev_vui_length + len('[]()')
            vui[0] -= displacement
            vui[1] -= displacement
            # No need to subtract the displacement from the URL part (indices 2 and 3)

        # When calculating the length, subtract 1 again not to include the previously called ']'
        entities.append(
            MessageEntityTextUrl(
                offset=vui[0], length=vui[1] - vui[0] - 1, url=link_url))

    # After the message is clean from links, handle all the indicator flags
    indicator_flags = {'*': None, '_': None, '`': None}

    # Iterate over the list to find the indicators of entities
    for i, c in enumerate(msg):
        # Only perform further check if the current character is an indicator
        if c in indicator_flags:
            # If it is the first time we find this indicator, update its index
            if indicator_flags[c] is None:
                indicator_flags[c] = i

            # Otherwise, it means that we found it before. Hence, the message entity *is* complete
            else:
                # Then we have found a new whole valid entity
                offset = indicator_flags[c]
                length = i - offset - 1  # Subtract -1 not to include the indicator itself

                # Add the corresponding entity
                if c == '*':
                    entities.append(
                        MessageEntityBold(
                            offset=offset, length=length))

                elif c == '_':
                    entities.append(
                        MessageEntityItalic(
                            offset=offset, length=length))

                elif c == '`':
                    entities.append(
                        MessageEntityCode(
                            offset=offset, length=length))

                # Clear the flag to start over with this indicator
                indicator_flags[c] = None

    # Sort the entities by their offset first
    entities = sorted(entities, key=lambda e: e.offset)

    # Now that all the entities have been found and sorted, remove
    # their indicators from the message and update the offsets
    for entity in entities:
        if type(entity) is not MessageEntityTextUrl:
            # Clean the message from the current entity's indicators
            del msg[entity.offset + entity.length + 1]
            del msg[entity.offset]

            # Iterate over all the entities but the current
            for sub_entity in [e for e in entities if e is not entity]:
                # First case, one in one out: so*me_th_in*g.
                # In this case, the current entity length is decreased by two,
                # and all the sub_entities offset decreases 1
                if (sub_entity.offset > entity.offset and
                        sub_entity.offset + sub_entity.length <
                        entity.offset + entity.length):
                    entity.length -= 2
                    sub_entity.offset -= 1

                # Second case, both inside: so*me_th*in_g.
                # In this case, the current entity length is decreased by one,
                # and all the sub_entities offset and length decrease 1
                elif (entity.offset < sub_entity.offset < entity.offset +
                      entity.length < sub_entity.offset + sub_entity.length):
                    entity.length -= 1
                    sub_entity.offset -= 1
                    sub_entity.length -= 1

                # Third case, both outside: so*me*th_in_g.
                # In this case, the current entity is left untouched,
                # and all the sub_entities offset decreases 2
                elif sub_entity.offset > entity.offset + entity.length:
                    sub_entity.offset -= 2

    # Finally, we can join our poor mutilated message back and return
    msg = ''.join(msg)
    return msg, entities
