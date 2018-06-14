//int ? = Int;
//long ? = Long;
//double ? = Double;
//string ? = String;

dummyHttpWait = HttpWait;

//vector {t:Type} # [ t ] = Vector t;

//int128 4*[ int ] = Int128;
//int256 8*[ int ] = Int256;

resPQ#05162463 nonce:int128 server_nonce:int128 pq:bytes server_public_key_fingerprints:Vector<long> = ResPQ;

p_q_inner_data#83c95aec pq:bytes p:bytes q:bytes nonce:int128 server_nonce:int128 new_nonce:int256 = P_Q_inner_data;
p_q_inner_data_temp#3c6a84d4 pq:bytes p:bytes q:bytes nonce:int128 server_nonce:int128 new_nonce:int256 expires_in:int = P_Q_inner_data;

server_DH_params_fail#79cb045d nonce:int128 server_nonce:int128 new_nonce_hash:int128 = Server_DH_Params;
server_DH_params_ok#d0e8075c nonce:int128 server_nonce:int128 encrypted_answer:bytes = Server_DH_Params;

server_DH_inner_data#b5890dba nonce:int128 server_nonce:int128 g:int dh_prime:bytes g_a:bytes server_time:int = Server_DH_inner_data;

client_DH_inner_data#6643b654 nonce:int128 server_nonce:int128 retry_id:long g_b:bytes = Client_DH_Inner_Data;

dh_gen_ok#3bcbf734 nonce:int128 server_nonce:int128 new_nonce_hash1:int128 = Set_client_DH_params_answer;
dh_gen_retry#46dc1fb9 nonce:int128 server_nonce:int128 new_nonce_hash2:int128 = Set_client_DH_params_answer;
dh_gen_fail#a69dae02 nonce:int128 server_nonce:int128 new_nonce_hash3:int128 = Set_client_DH_params_answer;

bind_auth_key_inner#75a3f765 nonce:long temp_auth_key_id:long perm_auth_key_id:long temp_session_id:long expires_at:int = BindAuthKeyInner;

//rpc_result#f35c6d01 req_msg_id:long result:bytes = RpcResult;
rpc_error#2144ca19 error_code:int error_message:string = RpcError;

rpc_answer_unknown#5e2ad36e = RpcDropAnswer;
rpc_answer_dropped_running#cd78e586 = RpcDropAnswer;
rpc_answer_dropped#a43ad8b7 msg_id:long seq_no:int bytes:int = RpcDropAnswer;

future_salt#0949d9dc valid_since:int valid_until:int salt:long = FutureSalt;
future_salts#ae500895 req_msg_id:long now:int salts:vector<future_salt> = FutureSalts;

pong#347773c5 msg_id:long ping_id:long = Pong;

destroy_session_ok#e22045fc session_id:long = DestroySessionRes;
destroy_session_none#62d350c9 session_id:long = DestroySessionRes;

new_session_created#9ec20908 first_msg_id:long unique_id:long server_salt:long = NewSession;

//msg_container#73f1f8dc messages:vector<%Message> = MessageContainer;
//message msg_id:long seqno:int bytes:int body:bytes = Message;
//msg_copy#e06046b2 orig_message:Message = MessageCopy;

//gzip_packed#3072cfa1 packed_data:bytes = Object;

msgs_ack#62d6b459 msg_ids:Vector<long> = MsgsAck;

bad_msg_notification#a7eff811 bad_msg_id:long bad_msg_seqno:int error_code:int = BadMsgNotification;
bad_server_salt#edab447b bad_msg_id:long bad_msg_seqno:int error_code:int new_server_salt:long = BadMsgNotification;

msg_resend_req#7d861a08 msg_ids:Vector<long> = MsgResendReq;
msgs_state_req#da69fb52 msg_ids:Vector<long> = MsgsStateReq;
msgs_state_info#04deb57d req_msg_id:long info:string = MsgsStateInfo;
msgs_all_info#8cc0d131 msg_ids:Vector<long> info:string = MsgsAllInfo;
msg_detailed_info#276d3ec6 msg_id:long answer_msg_id:long bytes:int status:int = MsgDetailedInfo;
msg_new_detailed_info#809db6df answer_msg_id:long bytes:int status:int = MsgDetailedInfo;

rsa_public_key n:string e:bytes = RSAPublicKey;

---functions---

req_pq_multi#be7e8ef1 nonce:int128 = ResPQ;

req_DH_params#d712e4be nonce:int128 server_nonce:int128 p:bytes q:bytes public_key_fingerprint:long encrypted_data:string = Server_DH_Params;

set_client_DH_params#f5045f1f nonce:int128 server_nonce:int128 encrypted_data:bytes = Set_client_DH_params_answer;

rpc_drop_answer#58e4a740 req_msg_id:long = RpcDropAnswer;
get_future_salts#b921bd04 num:int = FutureSalts;
ping#7abe77ec ping_id:long = Pong;
ping_delay_disconnect#f3427b8c ping_id:long disconnect_delay:int = Pong;
destroy_session#e7512126 session_id:long = DestroySessionRes;

http_wait#9299359f max_delay:int wait_after:int max_wait:int = HttpWait;

//test.useGzipPacked = GzipPacked;
//test.useServerDhInnerData = Server_DH_inner_data;
//test.useNewSessionCreated = NewSession;
//test.useMsgsAck = MsgsAck;
//test.useBadMsgNotification = BadMsgNotification;

//test.useOther key:rsa_public_key p_q_data:P_Q_inner_data dh_data:client_DH_inner_data = RpcError;
