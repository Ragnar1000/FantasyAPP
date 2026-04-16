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
        h_tabs = st.tabs(["🚑 EMERGENCY FIXER", "🏆 Tournaments", "➕ Manage Matches", "📊 Leaderboard", "🗑️ Users"])

        # Tab 1: EMERGENCY FIXER
        with h_tabs[0]:
            st.error("🚨 EMERGENCY DATABASE CLEANUP 🚨")
            
            st.subheader("Step 1: Nuclear Leaderboard Reset")
            st.info("This will set EVERY match back to 'PENDING'. This instantly drops everyone's score back to 0 without deleting their actual predictions.")
            if st.button("☢️ Reset All Matches to Pending (Zero Out Scores)", type="primary"):
                all_m = db.collection('matches').stream()
                for m in all_m:
                    m.reference.update({'winner': 'PENDING'})
                st.success("✅ All matches set to Pending. Leaderboard is now at 0.")
                st.rerun()
            
            st.divider()
            
            st.subheader("Step 2: Wipe Bad Math")
            st.info("This will delete any manual +1 or -1 point corrections you typed in earlier.")
            if st.button("🧹 Click Here to Wipe Manual Leaderboard Corrections"):
                adj_docs = db.collection('leaderboard_adjustments').stream()
                for doc in adj_docs:
                    doc.reference.delete()
                st.success("✅ All manual math wiped!")
                
            st.divider()
            
            st.subheader("Step 3: Database Match Viewer")
            st.info("Here is every match currently existing in your database. If a match is not in this list, it was permanently deleted and must be recreated.")
            
            all_matches = db.collection('matches').stream()
            matches_exist = False
            
            all_match_list = []
            for doc in all_matches:
                d = doc.to_dict()
                d['id'] = doc.id
                all_match_list.append(d)
                
            all_match_list.sort(key=lambda x: datetime.fromisoformat(x.get('deadline', datetime.now(PKT).isoformat())))
            
            for data in all_match_list:
                matches_exist = True
                m_id = data['id']
                status = data.get('winner', 'PENDING')
                t1 = data.get('team1', 'Team 1')
                t2 = data.get('team2', 'Team 2')
                
                try:
                    dead = datetime.fromisoformat(data['deadline'])
                    dead_str = dead.strftime('%b %d, %Y - %I:%M %p')
                except:
                    dead_str = "Unknown Time"
                
                with st.container(border=True):
                    st.write(f"### Match: `{m_id}`")
                    st.write(f"🕒 **Original Deadline:** {dead_str}")
                    
                    if status == "PENDING":
                        st.warning("Status: ⏳ PENDING")
                    else:
                        st.success(f"Status: 🔒 LOCKED (Winner: {status})")
                        
                    c1, c2, c3 = st.columns(3)
                    
                    if c1.button(f"🏆 Set Winner: {t1}", key=f"win1_{m_id}"):
                        db.collection('matches').document(m_id).update({'winner': t1})
                        st.rerun()
                        
                    if c2.button(f"🏆 Set Winner: {t2}", key=f"win2_{m_id}"):
                        db.collection('matches').document(m_id).update({'winner': t2})
                        st.rerun()
                        
                    if c3.button(f"🗑️ Delete Match Entirely", key=f"del_{m_id}"):
                        db.collection('matches').document(m_id).delete()
                        preds = db.collection('predictions').where('match_name', '==', m_id).stream()
                        for p in preds: p.reference.delete()
                        st.rerun()

            if not matches_exist:
                st.write("No matches exist in the database.")

        # Tab 2: Manage Tournaments
        with h_tabs[1]:
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
                    st.error(f"Confirm deleting '{del_t}'? (This WILL wipe all matches and predictions inside it)")
                    c1, c2 = st.columns(2)
                    if c1.button("Yes, Delete All", key="yes_dt"):
                        db.collection('tournaments').document(del_t).delete()
                        m_to_del = db.collection('matches').where('tournament', '==', del_t).stream()
                        for m in m_to_del: m.reference.delete()
                        p_to_del = db.collection('predictions').where('tournament', '==', del_t).stream()
                        for p in p_to_del: p.reference.delete()
                        st.session_state['confirm_del_t'] = False
                        st.rerun()
                    if c2.button("No", key="no_dt"):
                        st.session_state['confirm_del_t'] = False
                        st.rerun()
            else:
                st.info("No tournaments available.")

        # Tab 3: Create Matches
        with h_tabs[2]:
            st.subheader("Add New Match")
            if not active_tournaments:
                st.error("Please create a tournament first!")
            else:
                tourney = st.selectbox("Select Tournament", active_tournaments)
                t1, t2 = st.text_input("Team 1").strip(), st.text_input("Team 2").strip()
                d_date = st.date_input("Deadline Date")
                d_time = st.time_input("Deadline Time (PKT)")
                
                if st.button("Save Match"):
                    if t1 and t2:
                        dt = datetime.combine(d_date, d_time).replace(tzinfo=PKT).isoformat()
                        
                        # --- THE BUG FIX --- Date is attached to prevent overwriting
                        date_str = d_date.strftime('%b %d')
                        match_name = f"{t1} vs {t2} ({date_str})"
                        
                        db.collection('matches').document(match_name).set({
                            'tournament': tourney, 'team1': t1, 'team2': t2, 
                            'winner': "PENDING", 'deadline': dt
                        })
                        st.success(f"Match '{match_name}' saved!")
                        st.rerun()
                    else:
                        st.error("Please enter both team names.")

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
                        
                # Read manual adjustments
                adj_docs = db.collection('leaderboard_adjustments').where('tournament', '==', l_tourney).stream()
                for adj in adj_docs:
                    data = adj.to_dict()
                    u = data['username']
                    if u not in scores: scores[u] = {'W': 0, 'L': 0}
                    scores[u]['W'] += data.get('adj_w', 0)
                    scores[u]['L'] += data.get('adj_l', 0)
                        
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
                        
                # Factor in adjustments
                adj_docs = db.collection('leaderboard_adjustments').where('tournament', '==', user_l_tourney).stream()
                for adj in adj_docs:
                    data = adj.to_dict()
                    u = data['username']
                    if u not in scores: scores[u] = {'W': 0, 'L': 0}
                    scores[u]['W'] += data.get('adj_w', 0)
                    scores[u]['L'] += data.get('adj_l', 0)
                        
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
                    if h.get('tournament') not in active_tournaments:
                        continue
                        
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
                                    st.rerun()
                
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