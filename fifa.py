import streamlit as st
from datetime import datetime, timezone, timedelta
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. TIMEZONE & FIREBASE SETUP ---
PKT = timezone(timedelta(hours=5), name="PKT")

# Check if Firebase is already connected to avoid crashing
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error("⚠️ Firebase Secrets not found! Please check your Streamlit Settings.")
        st.stop()

db = firestore.client()

def get_tournaments():
    docs = db.collection('tournaments').stream()
    return sorted([doc.id for doc in docs])

# --- 2. SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['role'] = None
    st.session_state['username'] = ""

# --- 3. LOGIN & REGISTRATION ---
if not st.session_state['logged_in']:
    st.title("🏆 Fantasy App")
    tab1, tab2 = st.tabs(["Login", "Register Account"])
    
    with tab1:
        u_log = st.text_input("Username", key="l_u").strip()
        p_log = st.text_input("Password", type="password", key="l_p")
        remember_me = st.checkbox("Remember Me")
        
        if st.button("Login"):
            if u_log == "admin" and p_log == st.secrets.get("admin_password", "host123"):
                st.session_state.update({"logged_in": True, "role": "Host", "username": "Admin"})
                st.rerun()
            else:
                user_doc = db.collection('users').document(u_log).get()
                if user_doc.exists and user_doc.to_dict().get('password') == p_log:
                    st.session_state.update({"logged_in": True, "role": "User", "username": u_log})
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
                    
    with tab2:
        u_reg = st.text_input("New Username", key="r_u").strip()
        p_reg = st.text_input("New Password", type="password", key="r_p")
        if st.button("Register"):
            if u_reg and p_reg:
                if u_reg.lower() == "admin":
                    st.error("Cannot use that username.")
                else:
                    doc_ref = db.collection('users').document(u_reg)
                    if doc_ref.get().exists:
                        st.error("Username taken!")
                    else:
                        doc_ref.set({'password': p_reg})
                        st.success("Account created! Go to Login.")

# --- 4. THE MAIN APP ---
else:
    with st.sidebar:
        st.header(f"Logged in as: {st.session_state['username']}")
        st.write(f"🕒 PKT: {datetime.now(PKT).strftime('%I:%M %p')}")
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.session_state['role'] = None
            st.session_state['username'] = ""
            st.rerun()

    active_tournaments = get_tournaments()

    # ==========================================
    # HOST DASHBOARD
    # ==========================================
    if st.session_state['role'] == "Host":
        st.title("🛠️ Host Dashboard")
        h_tabs = st.tabs(["🏆 Tournaments", "➕ Manage Matches", "📋 Player Picks", "📊 Leaderboard", "🗑️ Users"])

        # Tab 1: Manage Tournaments
        with h_tabs[0]:
            st.subheader("Create a Tournament")
            new_t = st.text_input("New Tournament Name (e.g., BBL, World Cup)").strip()
            if st.button("Create Tournament"):
                st.session_state['confirm_create_t'] = True
                
            if st.session_state.get('confirm_create_t', False):
                st.warning(f"Confirm creating '{new_t}'?")
                c1, c2 = st.columns(2)
                if c1.button("Yes", key="yes_ct"):
                    if new_t:
                        doc_ref = db.collection('tournaments').document(new_t)
                        if not doc_ref.get().exists:
                            doc_ref.set({'created': True})
                            st.session_state['confirm_create_t'] = False
                            st.success("Tournament created!")
                            st.rerun()
                        else:
                            st.error("Tournament already exists!")
                if c2.button("No", key="no_ct"):
                    st.session_state['confirm_create_t'] = False
                    st.rerun()

            st.divider()
            st.subheader("Delete a Tournament")
            if active_tournaments:
                del_t = st.selectbox("Select Tournament to Delete", active_tournaments)
                if st.button("Delete Tournament"):
                    st.session_state['confirm_del_t'] = True
                    
                if st.session_state.get('confirm_del_t', False):
                    st.warning(f"Confirm deleting '{del_t}'? (This won't delete past matches)")
                    c1, c2 = st.columns(2)
                    if c1.button("Yes", key="yes_dt"):
                        db.collection('tournaments').document(del_t).delete()
                        st.session_state['confirm_del_t'] = False
                        st.rerun()
                    if c2.button("No", key="no_dt"):
                        st.session_state['confirm_del_t'] = False
                        st.rerun()
            else:
                st.info("No tournaments available.")

        # Tab 2: Create Matches & Set Winners
        with h_tabs[1]:
            st.subheader("Add New Match")
            if not active_tournaments:
                st.error("Please create a tournament first!")
            else:
                tourney = st.selectbox("Select Tournament", active_tournaments)
                t1, t2 = st.text_input("Team 1"), st.text_input("Team 2")
                d_date = st.date_input("Deadline Date")
                d_time = st.time_input("Deadline Time (PKT)")
                
                if st.button("Save Match"):
                    st.session_state['confirm_save_m'] = True
                    
                if st.session_state.get('confirm_save_m', False):
                    st.warning("Confirm creating this match?")
                    c1, c2 = st.columns(2)
                    if c1.button("Yes", key="yes_cm"):
                        dt = datetime.combine(d_date, d_time).replace(tzinfo=PKT).isoformat()
                        match_name = f"{t1} vs {t2}"
                        db.collection('matches').document(match_name).set({
                            'tournament': tourney, 'team1': t1, 'team2': t2, 
                            'winner': "PENDING", 'deadline': dt
                        })
                        st.session_state['confirm_save_m'] = False
                        st.success("Match saved!")
                        st.rerun()
                    if c2.button("No", key="no_cm"):
                        st.session_state['confirm_save_m'] = False
                        st.rerun()
            
            st.divider()
            st.subheader("Manage Existing Matches")
            if active_tournaments:
                m_tourney = st.selectbox("Select Tournament to Manage", active_tournaments, key="manage_t")
                
                pending_docs = db.collection('matches').where('tournament', '==', m_tourney).where('winner', '==', 'PENDING').stream()
                
                pending_list = []
                for doc in pending_docs:
                    data = doc.to_dict()
                    data['match_id'] = doc.id
                    pending_list.append(data)
                
                pending_list.sort(key=lambda x: datetime.fromisoformat(x['deadline']))
                
                if pending_list:
                    manage_tabs = st.tabs(["🏆 Set Winners", "🗑️ Delete Matches"])
                    
                    with manage_tabs[0]:
                        for m_data in pending_list:
                            m_name = m_data['match_id']
                            dead = datetime.fromisoformat(m_data['deadline'])
                            st.write(f"**{m_name}** | Deadline: {dead.strftime('%b %d, %I:%M %p')}")
                            
                            col1, col2 = st.columns([2, 1])
                            win = col1.selectbox("Winner", [m_data['team1'], m_data['team2']], key=f"host_win_{m_name}", label_visibility="collapsed")
                            
                            if col2.button("Lock Winner", key=f"host_btn_{m_name}"):
                                st.session_state[f'confirm_lock_{m_name}'] = True
                                
                            if st.session_state.get(f'confirm_lock_{m_name}', False):
                                st.warning(f"Confirm locking '{win}' as winner for {m_name}?")
                                c1, c2 = st.columns(2)
                                if c1.button("Yes", key=f"y_lock_{m_name}"):
                                    db.collection('matches').document(m_name).update({'winner': win})
                                    st.session_state[f'confirm_lock_{m_name}'] = False
                                    st.rerun()
                                if c2.button("No", key=f"n_lock_{m_name}"):
                                    st.session_state[f'confirm_lock_{m_name}'] = False
                                    st.rerun()
                                    
                    with manage_tabs[1]:
                        for m_data in pending_list:
                            m_name = m_data['match_id']
                            dead = datetime.fromisoformat(m_data['deadline'])
                            
                            col1, col2 = st.columns([2, 1])
                            col1.write(f"**{m_name}** | {dead.strftime('%b %d, %I:%M %p')}")
                            
                            if col2.button("Delete Match", key=f"host_del_{m_name}"):
                                st.session_state[f'confirm_del_m_{m_name}'] = True
                                
                            if st.session_state.get(f'confirm_del_m_{m_name}', False):
                                st.error(f"Confirm deleting '{m_name}'? This wipes user predictions.")
                                c1, c2 = st.columns(2)
                                if c1.button("Yes, Delete", key=f"y_del_{m_name}"):
                                    db.collection('matches').document(m_name).delete()
                                    preds = db.collection('predictions').where('match_name', '==', m_name).stream()
                                    for p in preds: p.reference.delete()
                                    st.session_state[f'confirm_del_m_{m_name}'] = False
                                    st.rerun()
                                if c2.button("No, Cancel", key=f"n_del_{m_name}"):
                                    st.session_state[f'confirm_del_m_{m_name}'] = False
                                    st.rerun()
                else:
                    st.info("No pending matches to manage for this tournament.")

        # Tab 3: Player Picks
        with h_tabs[2]:
            st.subheader("Player Predictions by Match")
            if not active_tournaments:
                st.info("No tournaments available.")
            else:
                view_tourney = st.radio("Select Tournament", active_tournaments, horizontal=True, key="host_picks_t")
                
                m_docs = db.collection('matches').where('tournament', '==', view_tourney).stream()
                m_list = []
                for doc in m_docs:
                    d = doc.to_dict()
                    d['match_id'] = doc.id
                    m_list.append(d)
                
                if m_list:
                    m_list.sort(key=lambda x: datetime.fromisoformat(x['deadline']))
                    match_options = [m['match_id'] for m in m_list]
                    
                    pick_m_sel = st.selectbox("Select Match (Nearest Deadline First)", match_options, key="host_picks_m")
                    
                    picks = db.collection('predictions').where('match_name', '==', pick_m_sel).stream()
                    picks_data = [p.to_dict() for p in picks]
                    
                    if picks_data:
                        st.table([{"Player": p['username'], "Their Pick": p['user_guess']} for p in picks_data])
                    else:
                        st.info("No predictions made for this match yet.")
                else:
                    st.info("No matches found for this tournament.")

        # Tab 4: HOST LEADERBOARD
        with h_tabs[3]:
            st.subheader("Current Rankings")
            if active_tournaments:
                l_tourney = st.selectbox("Select Tournament Leaderboard", active_tournaments, key="host_lead")
                
                m_docs = db.collection('matches').where('tournament', '==', l_tourney).stream()
                completed = {m.id: m.to_dict()['winner'] for m in m_docs if m.to_dict().get('winner') != 'PENDING'}
                
                p_docs = db.collection('predictions').where('tournament', '==', l_tourney).stream()
                
                scores = {}
                for p in p_docs:
                    data = p.to_dict()
                    user, match, guess = data['username'], data['match_name'], data['user_guess']
                    if user not in scores: scores[user] = {'W': 0, 'L': 0}
                    if match in completed:
                        if guess == completed[match]: scores[user]['W'] += 1
                        else: scores[user]['L'] += 1
                        
                if scores:
                    sorted_scores = sorted([{"Player": k, "Wins": v['W'], "Losses": v['L']} for k, v in scores.items()], key=lambda x: x['Wins'], reverse=True)
                    st.table(sorted_scores)
                else:
                    st.info(f"No completed matches for {l_tourney} yet.")

        # Tab 5: MANAGE USERS
        with h_tabs[4]:
            st.subheader("Remove Users")
            users = [u.id for u in db.collection('users').stream() if u.id != 'admin']
            if users:
                user_to_delete = st.selectbox("Select user to remove", users)
                if st.button("Delete User"):
                    st.session_state['confirm_del_u'] = True
                    
                if st.session_state.get('confirm_del_u', False):
                    st.warning(f"Confirm completely deleting user '{user_to_delete}'?")
                    c1, c2 = st.columns(2)
                    if c1.button("Yes", key="y_du"):
                        db.collection('users').document(user_to_delete).delete()
                        preds = db.collection('predictions').where('username', '==', user_to_delete).stream()
                        for p in preds: p.reference.delete()
                        st.session_state['confirm_del_u'] = False
                        st.success(f"User {user_to_delete} deleted!")
                        st.rerun()
                    if c2.button("No", key="n_du"):
                        st.session_state['confirm_del_u'] = False
                        st.rerun()
            else:
                st.info("No registered users found.")

    # ==========================================
    # USER DASHBOARD
    # ==========================================
    else:
        u_tabs = st.tabs(["🎮 Predict", "🏆 Leaderboard", "👤 Profile & History"])
        
        with u_tabs[0]:
            st.title("Fantasy Predictions")
            if not active_tournaments:
                st.warning("The host hasn't created any tournaments yet.")
            else:
                p_tourney = st.radio("Select Tournament", active_tournaments, horizontal=True)
                st.divider()
                
                all_matches = {m.id: m.to_dict() for m in db.collection('matches').where('tournament', '==', p_tourney).where('winner', '==', 'PENDING').stream()}
                user_preds = [p.to_dict()['match_name'] for p in db.collection('predictions').where('username', '==', st.session_state['username']).where('tournament', '==', p_tourney).stream()]
                available_matches = {k: v for k, v in all_matches.items() if k not in user_preds}
                
                if not available_matches:
                    st.success("🎉 You are all caught up! Check the 'Profile & History' tab.")
                else:
                    st.info(f"You have {len(available_matches)} match(es) left to predict in {p_tourney}.")
                    
                    sorted_matches = sorted(available_matches.items(), key=lambda x: datetime.fromisoformat(x[1]['deadline']))
                    
                    with st.container(height=600):
                        for m_sel, m_data in sorted_matches:
                            st.markdown(f"### **{m_sel}**")
                            dead = datetime.fromisoformat(m_data['deadline'])
                            st.write(f"Deadline: **{dead.strftime('%b %d, %I:%M %p')}**")
                            
                            if datetime.now(PKT) > dead:
                                st.error("Closed!")
                            else:
                                pick = st.radio("Choose option:", [m_data['team1'], m_data['team2']], key=f"user_pick_{m_sel}")
                                
                                if st.button("Predict", key=f"btn_pick_{m_sel}"):
                                    db.collection('predictions').add({
                                        'username': st.session_state['username'],
                                        'match_name': m_sel,
                                        'user_guess': pick,
                                        'tournament': p_tourney
                                    })
                                    st.rerun()
                            st.divider()
                                        
        with u_tabs[1]:
            st.title("Leaderboards")
            if active_tournaments:
                user_l_tourney = st.selectbox("Select Tournament Leaderboard", active_tournaments, key="user_lead")
                
                m_docs = db.collection('matches').where('tournament', '==', user_l_tourney).stream()
                completed = {m.id: m.to_dict()['winner'] for m in m_docs if m.to_dict().get('winner') != 'PENDING'}
                
                p_docs = db.collection('predictions').where('tournament', '==', user_l_tourney).stream()
                
                scores = {}
                for p in p_docs:
                    data = p.to_dict()
                    user, match, guess = data['username'], data['match_name'], data['user_guess']
                    if user not in scores: scores[user] = {'W': 0, 'L': 0}
                    if match in completed:
                        if guess == completed[match]: scores[user]['W'] += 1
                        else: scores[user]['L'] += 1
                        
                if scores:
                    sorted_scores = sorted([{"User": k, "Wins": v['W'], "Losses": v['L']} for k, v in scores.items()], key=lambda x: x['Wins'], reverse=True)
                    st.table(sorted_scores)
                else:
                    st.info(f"No completed matches for {user_l_tourney} yet.")
                    
        with u_tabs[2]:
            st.title("👤 Profile & History")
            hist_docs = db.collection('predictions').where('username', '==', st.session_state['username']).stream()
            hist_data = []
            for doc in hist_docs:
                d = doc.to_dict()
                d['doc_id'] = doc.id
                hist_data.append(d)
                
            if hist_data:
                m_docs = {m.id: m.to_dict() for m in db.collection('matches').stream()}
                editable_picks = []
                locked_picks = []
                
                for h in hist_data:
                    m_info = m_docs.get(h['match_name'])
                    if m_info:
                        dead = datetime.fromisoformat(m_info['deadline'])
                        actual_winner = m_info.get('winner', 'PENDING')
                        if datetime.now(PKT) < dead and actual_winner == 'PENDING':
                            editable_picks.append((h, m_info))
                        else:
                            locked_picks.append((h, m_info))
                
                editable_picks.sort(key=lambda x: datetime.fromisoformat(x[1]['deadline']))
                
                if editable_picks:
                    st.subheader("✏️ Editable Predictions")
                    st.info("You can change these picks until the match deadline.")
                    for h, m_info in editable_picks:
                        m_name = h['match_name']
                        dead = datetime.fromisoformat(m_info['deadline'])
                        
                        with st.expander(f"{m_name} (Deadline: {dead.strftime('%b %d, %I:%M %p')})"):
                            st.write(f"Current Pick: **{h['user_guess']}**")
                            options = [m_info['team1'], m_info['team2']]
                            curr_idx = options.index(h['user_guess']) if h['user_guess'] in options else 0
                            new_pick = st.radio("Change pick to:", options, index=curr_idx, key=f"edit_{h['doc_id']}")
                            
                            if st.button("Update Pick", key=f"btn_edit_{h['doc_id']}"):
                                if new_pick != h['user_guess']:
                                    db.collection('predictions').document(h['doc_id']).update({'user_guess': new_pick})
                                    st.success("Pick updated!")
                                    st.rerun()
                                else:
                                    st.warning("You already selected this team.")
                
                st.divider()
                st.subheader("📜 Past & Locked Predictions")
                if locked_picks:
                    table_data = []
                    for h, m_info in locked_picks:
                        actual_winner = m_info.get('winner', 'PENDING')
                        status = "⏳ Locked (Awaiting Result)" if actual_winner == 'PENDING' else ("✅ Won" if h['user_guess'] == actual_winner else "❌ Lost")
                        table_data.append({
                            "Tournament": h['tournament'], "Match": h['match_name'], 
                            "Your Pick": h['user_guess'], "Status": status
                        })
                    st.table(table_data)
                else:
                    st.info("No locked predictions yet.")
            else:
                st.info("You haven't made any predictions yet.")