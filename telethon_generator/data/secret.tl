// layer 8

secret.decryptedMessage8#1f814f1f random_id:long random_bytes:bytes message:string media:DecryptedMessageMedia = secret.DecryptedMessage;
secret.decryptedMessageService8#aa48327d random_id:long random_bytes:bytes action:DecryptedMessageAction = secret.DecryptedMessage;
secret.decryptedMessageMediaEmpty#89f5c4a = secret.DecryptedMessageMedia;
secret.decryptedMessageMediaPhoto23#32798a8c thumb:bytes thumb_w:int thumb_h:int w:int h:int size:int key:bytes iv:bytes = secret.DecryptedMessageMedia;
secret.decryptedMessageMediaVideo8#4cee6ef3 thumb:bytes thumb_w:int thumb_h:int duration:int w:int h:int size:int key:bytes iv:bytes = secret.DecryptedMessageMedia;
secret.decryptedMessageMediaGeoPoint#35480a59 lat:double long:double = secret.DecryptedMessageMedia;
secret.decryptedMessageMediaContact#588a0a97 phone_number:string first_name:string last_name:string user_id:int = secret.DecryptedMessageMedia;
secret.decryptedMessageActionSetMessageTTL#a1733aec ttl_seconds:int = secret.DecryptedMessageAction;
secret.decryptedMessageMediaDocument23#b095434b thumb:bytes thumb_w:int thumb_h:int file_name:string mime_type:string size:int key:bytes iv:bytes = secret.DecryptedMessageMedia;
secret.decryptedMessageMediaAudio8#6080758f duration:int size:int key:bytes iv:bytes = secret.DecryptedMessageMedia;
secret.decryptedMessageActionReadMessages#c4f40be random_ids:Vector<long> = secret.DecryptedMessageAction;
secret.decryptedMessageActionDeleteMessages#65614304 random_ids:Vector<long> = secret.DecryptedMessageAction;
secret.decryptedMessageActionScreenshotMessages#8ac1f475 random_ids:Vector<long> = secret.DecryptedMessageAction;
secret.decryptedMessageActionFlushHistory#6719e45c = secret.DecryptedMessageAction;

// layer 23

secret.decryptedMessage23#204d3878 random_id:long ttl:int message:string media:DecryptedMessageMedia = secret.DecryptedMessage;
secret.decryptedMessageService#73164160 random_id:long action:DecryptedMessageAction = secret.DecryptedMessage;
secret.decryptedMessageMediaVideo23#524a415d thumb:bytes thumb_w:int thumb_h:int duration:int mime_type:string w:int h:int size:int key:bytes iv:bytes = secret.DecryptedMessageMedia;
secret.decryptedMessageMediaAudio#57e0a9cb duration:int mime_type:string size:int key:bytes iv:bytes = secret.DecryptedMessageMedia;
secret.decryptedMessageLayer#1be31789 random_bytes:bytes layer:int in_seq_no:int out_seq_no:int message:DecryptedMessage = secret.DecryptedMessageLayer;

secret.sendMessageTypingAction#16bf744e = secret.SendMessageAction;
secret.sendMessageCancelAction#fd5ec8f5 = secret.SendMessageAction;
secret.sendMessageRecordVideoAction#a187d66f = secret.SendMessageAction;
secret.sendMessageUploadVideoAction#92042ff7 = secret.SendMessageAction;
secret.sendMessageRecordAudioAction#d52f73f7 = secret.SendMessageAction;
secret.sendMessageUploadAudioAction#e6ac8a6f = secret.SendMessageAction;
secret.sendMessageUploadPhotoAction#990a3c1a = secret.SendMessageAction;
secret.sendMessageUploadDocumentAction#8faee98e = secret.SendMessageAction;
secret.sendMessageGeoLocationAction#176f8ba1 = secret.SendMessageAction;
secret.sendMessageChooseContactAction#628cbc6f = secret.SendMessageAction;

secret.decryptedMessageActionResend#511110b0 start_seq_no:int end_seq_no:int = secret.DecryptedMessageAction;
secret.decryptedMessageActionNotifyLayer#f3048883 layer:int = secret.DecryptedMessageAction;
secret.decryptedMessageActionTyping#ccb27641 action:SendMessageAction = secret.DecryptedMessageAction;

secret.decryptedMessageActionRequestKey#f3c9611b exchange_id:long g_a:bytes = secret.DecryptedMessageAction;
secret.decryptedMessageActionAcceptKey#6fe1735b exchange_id:long g_b:bytes key_fingerprint:long = secret.DecryptedMessageAction;
secret.decryptedMessageActionAbortKey#dd05ec6b exchange_id:long = secret.DecryptedMessageAction;
secret.decryptedMessageActionCommitKey#ec2e0b9b exchange_id:long key_fingerprint:long = secret.DecryptedMessageAction;
secret.decryptedMessageActionNoop#a82fdd63 = secret.DecryptedMessageAction;

secret.documentAttributeImageSize#6c37c15c w:int h:int = secret.DocumentAttribute;
secret.documentAttributeAnimated#11b58939 = secret.DocumentAttribute;
secret.documentAttributeSticker23#fb0a5727 = secret.DocumentAttribute;
secret.documentAttributeVideo#5910cccb duration:int w:int h:int = secret.DocumentAttribute;
secret.documentAttributeAudio23#51448e5 duration:int = secret.DocumentAttribute;
secret.documentAttributeFilename#15590068 file_name:string = secret.DocumentAttribute;
secret.photoSizeEmpty#e17e23c type:string = secret.PhotoSize;
secret.photoSize#77bfb61b type:string location:FileLocation w:int h:int size:int = secret.PhotoSize;
secret.photoCachedSize#e9a734fa type:string location:FileLocation w:int h:int bytes:bytes = secret.PhotoSize;
secret.fileLocationUnavailable#7c596b46 volume_id:long local_id:int secret:long = secret.FileLocation;
secret.fileLocation#53d69076 dc_id:int volume_id:long local_id:int secret:long = secret.FileLocation;
secret.decryptedMessageMediaExternalDocument#fa95b0dd id:long access_hash:long date:int mime_type:string size:int thumb:PhotoSize dc_id:int attributes:Vector<DocumentAttribute> = secret.DecryptedMessageMedia;

// layer 45

secret.documentAttributeAudio45#ded218e0 duration:int title:string performer:string = secret.DocumentAttribute;

// layer 46

secret.decryptedMessage46#36b091de flags:# random_id:long ttl:int message:string media:flags.9?DecryptedMessageMedia entities:flags.7?Vector<MessageEntity> via_bot_name:flags.11?string reply_to_random_id:flags.3?long = secret.DecryptedMessage;
secret.decryptedMessageMediaPhoto#f1fa8d78 thumb:bytes thumb_w:int thumb_h:int w:int h:int size:int key:bytes iv:bytes caption:string = secret.DecryptedMessageMedia;
secret.decryptedMessageMediaVideo#970c8c0e thumb:bytes thumb_w:int thumb_h:int duration:int mime_type:string w:int h:int size:int key:bytes iv:bytes caption:string = secret.DecryptedMessageMedia;
secret.decryptedMessageMediaDocument#7afe8ae2 thumb:bytes thumb_w:int thumb_h:int mime_type:string size:int key:bytes iv:bytes attributes:Vector<DocumentAttribute> caption:string = secret.DecryptedMessageMedia;
secret.documentAttributeSticker#3a556302 alt:string stickerset:InputStickerSet = secret.DocumentAttribute;
secret.documentAttributeAudio#9852f9c6 flags:# voice:flags.10?true duration:int title:flags.0?string performer:flags.1?string waveform:flags.2?bytes = secret.DocumentAttribute;
secret.messageEntityUnknown#bb92ba95 offset:int length:int = secret.MessageEntity;
secret.messageEntityMention#fa04579d offset:int length:int = secret.MessageEntity;
secret.messageEntityHashtag#6f635b0d offset:int length:int = secret.MessageEntity;
secret.messageEntityBotCommand#6cef8ac7 offset:int length:int = secret.MessageEntity;
secret.messageEntityUrl#6ed02538 offset:int length:int = secret.MessageEntity;
secret.messageEntityEmail#64e475c2 offset:int length:int = secret.MessageEntity;
secret.messageEntityBold#bd610bc9 offset:int length:int = secret.MessageEntity;
secret.messageEntityItalic#826f8b60 offset:int length:int = secret.MessageEntity;
secret.messageEntityCode#28a20571 offset:int length:int = secret.MessageEntity;
secret.messageEntityPre#73924be0 offset:int length:int language:string = secret.MessageEntity;
secret.messageEntityTextUrl#76a6d327 offset:int length:int url:string = secret.MessageEntity;
secret.messageEntityMentionName#352dca58 offset:int length:int user_id:int = secret.MessageEntity;
secret.messageEntityPhone#9b69e34b offset:int length:int = secret.MessageEntity;
secret.messageEntityCashtag#4c4e743f offset:int length:int = secret.MessageEntity;
secret.inputStickerSetShortName#861cc8a0 short_name:string = secret.InputStickerSet;
secret.inputStickerSetEmpty#ffb62b95 = secret.InputStickerSet;
secret.decryptedMessageMediaVenue#8a0df56f lat:double long:double title:string address:string provider:string venue_id:string = secret.DecryptedMessageMedia;
secret.decryptedMessageMediaWebPage#e50511d8 url:string = secret.DecryptedMessageMedia;

// layer 66

secret.sendMessageRecordRoundAction#88f27fbc = secret.SendMessageAction;
secret.sendMessageUploadRoundAction#bb718624 = secret.SendMessageAction;
secret.documentAttributeVideo66#ef02ce6 flags:# round_message:flags.0?true duration:int w:int h:int = secret.DocumentAttribute;

// layer 73

secret.decryptedMessage#91cc4674 flags:# random_id:long ttl:int message:string media:flags.9?DecryptedMessageMedia entities:flags.7?Vector<MessageEntity> via_bot_name:flags.11?string reply_to_random_id:flags.3?long grouped_id:flags.17?long = secret.DecryptedMessage;

// layer 101

secret.messageEntityUnderline#9c4e7e8b offset:int length:int = secret.MessageEntity;
secret.messageEntityStrike#bf0693d4 offset:int length:int = secret.MessageEntity;
secret.messageEntityBlockquote#20df5d0 offset:int length:int = secret.MessageEntity;

---functions---

test.dummyFunction = secret.Bool;