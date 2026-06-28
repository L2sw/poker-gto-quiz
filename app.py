import streamlit as st
import random
import pandas as pd
import eval7

# ページの設定
st.set_page_config(page_title="GTO特訓ツール（ガチ仕様）", page_icon="🃏", layout="centered")

POSITION_RULES = {
    "UTG": {"open": ["紺", "赤", "黄"]},
    "HJ":  {"open": ["紺", "赤", "黄", "緑"]},
    "CO":  {"open": ["紺", "赤", "黄", "緑", "水色"]},
    "BTN": {"open": ["紺", "赤", "黄", "緑", "水色", "白", "グレー＋紫枠"]},
    "SB":  {"open": ["紺", "赤", "黄", "緑", "水色", "白"]},
    "BB":  {"open": ["紺", "赤", "黄", "緑", "水色", "白"]}
}

ALL_COLORS = ["薄ピンク", "グレー＋紫枠", "白", "水色", "緑", "黄", "赤", "紺"]
POSITIONS_LIST = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]

@st.cache_data
def load_ranges_from_csv(csv_path="poker_range_list.csv"):
    try:
        df = pd.read_csv(csv_path)
        return dict(zip(df['hand'], df['color']))
    except:
        return {"AA": "紺", "AKo": "赤", "AQs": "赤", "AhJh": "黄", "KhQh": "緑", "76s": "水色"}

def convert_to_concrete_cards(hand_str):
    ranks = "23456789TJQKA"
    suits = "shcd"
    r1, r2 = hand_str[0], hand_str[1]
    is_suited, is_offsuit = hand_str.endswith('s'), hand_str.endswith('o')
    combos = []
    if r1 == r2:
        for i in range(4):
            for j in range(i + 1, 4): combos.append([r1 + suits[i], r2 + suits[j]])
    elif is_suited:
        for s in suits: combos.append([r1 + s, r2 + s])
    elif is_offsuit or (not is_suited and not is_offsuit):
        for s1 in suits:
            for s2 in suits:
                if s1 != s2: combos.append([r1 + s1, r2 + s2])
    return combos

def get_range_combos(target_colors, hand_to_color):
    all_combos = []
    for hand, color in hand_to_color.items():
        if color in target_colors: all_combos.extend(convert_to_concrete_cards(hand))
    return all_combos

def determine_dynamic_ranges(hero_pos, villain_pos):
    hero_open_colors = POSITION_RULES[hero_pos]["open"]
    if villain_pos == "BB":
        return ALL_COLORS[max(0, ALL_COLORS.index(hero_open_colors[-1]) - 1):]
    if villain_pos == "SB":
        return ALL_COLORS[ALL_COLORS.index(hero_open_colors[-1]):]
    return ALL_COLORS[min(len(ALL_COLORS) - 1, ALL_COLORS.index(hero_open_colors[-1]) + 1):]

# ガチ仕様：iterations=10000 
def run_simulation(hero_combos, villain_combos, board, iterations=10000):
    if not hero_combos or not villain_combos: return 0.5
    hero_wins, villain_wins, ties = 0, 0, 0
    actual_iterations = 0
    deck_base = [eval7.Card(f"{r}{s}") for r in "23456789TJQKA" for s in "shcd"]
    for _ in range(iterations):
        h_cards_raw = random.choice(hero_combos)
        v_cards_raw = random.choice(villain_combos)
        h_cards = [eval7.Card(c) for c in h_cards_raw]
        v_cards = [eval7.Card(c) for c in v_cards_raw]
        used_cards = set(h_cards + v_cards + board)
        if len(used_cards) != len(h_cards) + len(v_cards) + len(board): continue
        actual_iterations += 1
        remaining_deck = [c for c in deck_base if c not in used_cards]
        num_to_draw = 5 - len(board)
        interim_board = board + random.sample(remaining_deck, num_to_draw) if num_to_draw > 0 else board
        hero_score = eval7.evaluate(h_cards + interim_board)
        villain_score = eval7.evaluate(v_cards + interim_board)
        if hero_score > villain_score: hero_wins += 1
        elif villain_score > hero_score: villain_wins += 1
        else: ties += 1
    return (hero_wins + 0.5 * ties) / actual_iterations if actual_iterations > 0 else 0.0

def is_hero_oop(hero_pos, villain_pos):
    order = ["SB", "BB", "UTG", "HJ", "CO", "BTN"]
    return order.index(hero_pos) < order.index(villain_pos)

hand_to_color = load_ranges_from_csv()

# セッション状態の安全初期化
if "game_state" not in st.session_state:
    st.session_state.game_state = "setup"
if "selected_pos" not in st.session_state:
    st.session_state.selected_pos = "ランダム"
if "quiz_phase" not in st.session_state:
    st.session_state.quiz_phase = 1 # 1: 第1決断, 2: 相手の対抗に対する第2決断
if "quiz_answered" not in st.session_state:
    st.session_state.quiz_answered = False

st.title("🃏 GTOクイズ特訓アプリ (ガチ仕様)")

# --- 1. セットアップ画面 ---
if st.session_state.game_state == "setup":
    st.subheader("🛠️ トレーニング設定")
    pos_choice = st.selectbox(
        "練習したい自分のポジション(Hero)を選択してください:", 
        ["ランダム", "UTG", "HJ", "CO", "BTN (後攻の練習に最適)", "SB (先攻の練習に最適)", "BB"],
        key="pos_select"
    )
    
    if st.button("ゲームに挑む 🚀", use_container_width=True, key="start_btn"):
        clean_choice = pos_choice.split(" ")[0]
        if clean_choice == "ランダム":
            hero_pos = random.choice(POSITIONS_LIST)
        else:
            hero_pos = clean_choice
            
        villain_pos = random.choice([p for p in POSITIONS_LIST if p != hero_pos])
        
        allowed_colors = POSITION_RULES[hero_pos]["open"]
        chosen_hand_format = random.choice([h for h, c in hand_to_color.items() if c in allowed_colors])
        hero_hand_pair = random.choice(convert_to_concrete_cards(chosen_hand_format))
        hero_hand_raw = f"{hero_hand_pair[0]}{hero_hand_pair[1]}"
        hero_color = hand_to_color[chosen_hand_format]
        villain_colors = determine_dynamic_ranges(hero_pos, villain_pos)
        
        deck = [f"{r}{s}" for r in "23456789TJQKA" for s in "shcd" if f"{r}{s}" not in hero_hand_pair]
        random.shuffle(deck)
        
        st.session_state.game_data = {
            "hero_pos": hero_pos,
            "villain_pos": villain_pos,
            "hero_hand_raw": hero_hand_raw,
            "hero_color": hero_color,
            "villain_colors": villain_colors,
            "deck": deck,
            "board": [],
            "pot": 5.5,
            "street_history": {},
            "current_street": "flop",
            "oop_action_taken": None,
            "villain_action_text": ""
        }
        st.session_state.game_state = "quiz_loop"
        st.session_state.quiz_phase = 1
        st.session_state.quiz_answered = False
        st.rerun()

# --- 2. ガチクイズコア画面 ---
elif st.session_state.game_state == "quiz_loop":
    data = st.session_state.game_data
    street = data["current_street"]
    hero_oop = is_hero_oop(data["hero_pos"], data["villain_pos"])
    
    # カードのストリート配布制御
    if street == "flop" and len(data["board"]) == 0:
        data["board"] = [data["deck"].pop() for _ in range(3)]
    elif street == "turn" and len(data["board"]) == 3:
        data["board"].append(data["deck"].pop())
    elif street == "river" and len(data["board"]) == 4:
        data["board"].append(data["deck"].pop())
        
    st.markdown(f"### ⚔️ 【クイズ】{street.upper()} (現在のポット: {data['pot']:.1f}bb)")
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**あなた (Hero)**: `{data['hero_pos']}` (【{data['hero_color']}】レンジ)")
            st.markdown(f"**手札**: `{data['hero_hand_raw']}` | ポジション: `{'先攻(OOP)' if hero_oop else '後攻(IP)'}`")
        with col2:
            st.markdown(f"**相手 (Villain)**: `{data['villain_pos']}`")
            st.markdown(f"**敵レンジ**: {', '.join(data['villain_colors'])}")
            
    st.info(f"📁 **現在のボード**: `{' '.join(data['board'])}`  |  💰 **ポット**: {data['pot']:.1f}bb")
    
    # ガチ確率の計算 (モンテカルロ10000回)
    hero_single_combo = [[data['hero_hand_raw'][0:2], data['hero_hand_raw'][2:4]]]
    hero_range_combos = get_range_combos([data['hero_color']], hand_to_color)
    villain_range_combos = get_range_combos(data['villain_colors'], hand_to_color)
    board_obj = [eval7.Card(c) for c in data['board']]
    
    with st.spinner("🧠 10,000回ガチGTOシミュレーション実行中..."):
        hand_eq = run_simulation(hero_single_combo, villain_range_combos, board_obj, iterations=10000)
        range_eq = run_simulation(hero_range_combos, villain_range_combos, board_obj, iterations=10000)
        
    # PC版と同じ比率・勝率のダッシュボード表示
    c_eq1, c_eq2 = st.columns(2)
    c_eq1.metric(label="📊 あなたのハンド勝率", value=f"{hand_eq*100:.1f} %")
    c_eq2.metric(label="📈 レンジ全体の勝率", value=f"{range_eq*100:.1f} %")
    st.markdown("---")
    
    hero_bet_count = list(data["street_history"].values()).count("bet")
    barrel_count = list(data["street_history"].values()).count("villain_bet")
    
    # --- パターンA: 【先攻(OOP)】の処理群 ---
    if hero_oop:
        if st.session_state.quiz_phase == 1:
            st.write("⚠️ あなたは**【先攻(OOP)】**です。最初にアクションを決めてしてください。")
            
            # GTO正解ロジック（PC版と完全一致）
            if street == "river":
                best_act = 3 if (hand_eq >= 0.85 and hero_bet_count >= 1) else (3 if barrel_count > 0 else (2 if hand_eq >= 0.70 else (1 if hand_eq >= 0.58 else 3)))
            else:
                if hand_eq >= 0.68: best_act = 2 if (range_eq >= 0.52 and hand_eq < 0.85) else 1
                elif hand_eq >= 0.56: best_act = 1
                elif hand_eq < 0.33 and range_eq >= 0.53: best_act = 1
                else: best_act = 3
                
            options = ["1: 小さくベットする (ポットの33%)", "2: 大きくベットする (ポットの66%〜75%)", "3: チェックする"]
            ans = st.radio("👉 番号を選択してください:", options, key=f"oop_p1_{street}")
            choice = int(ans[0])
            
            if not st.session_state.quiz_answered:
                if st.button("決断を確定する 🤝", use_container_width=True, key=f"btn_oop_p1_{street}"):
                    if choice != best_act:
                        st.error("❌ 不正解！レンジ特性、またはショーダウンバリュー(SDV)の保護の観点から最適ではありません。")
                    else:
                        st.session_state.quiz_answered = True
                        st.success("✨ 【正解です！】")
                        st.markdown("### 💡 【GTO戦略解説 (OOP / {})】".format(street.upper()))
                        if best_act == 3 and hand_eq >= 0.85:
                            st.info(f"➔ 【至高のトラップ（チェックインデュース）】勝率 {hand_eq*100:.1f}% の無敵のモンスターハンドです！ここで3発目のベットを打つと相手の引き締まったレンジ（QQ+やAK）は警戒して逃げてしまいます。あえてチェックして弱気を見せることで、相手のブラフや薄いバリューベットを強烈に誘い出す（インデュース）のがGTO最高EVのアクションです。")
                        elif best_act == 2:
                            st.info(f"➔ ハンド勝率が {hand_eq*100:.1f}% と圧倒的に高く、レンジも有利なため、相手のミドルペアやドローから最大限のバリューを回収すべき局面です（ラージベット）。")
                        elif best_act == 1:
                            if hand_eq >= 0.85:
                                st.info(f"➔ 【コミットメント誘導のスモールベット】勝率 {hand_eq*100:.1f}% の超モンスターハンドですが、ボードがJのペアなどで相手のレンジ（赤・紺）を過剰に警戒させて逃がしてしまうリスクがあります。あえて33%と小さく打つことで、相手のQQやKK、ドローをズルズルとコールに巻き込むのが最適戦略となります。")
                            elif hand_eq >= 0.56:
                                st.info(f"➔ 勝率は十分（{hand_eq*100:.1f}%）ですが、ボードが危険、またはレンジがやや不利なため、マージナルバリュー（薄いバリュー）を狙って小さく打つのが最適です。")
                            else:
                                st.info(f"➔ あなたのハンド単体は弱いですが、レンジ全体の勝率が {range_eq*100:.1f}% と有利なため、先攻からレンジを盾にボードを支配する『プロテクション/ブラフCB』を仕掛けるのが効果的です。")
                        elif best_act == 3:
                            st.info(f"➔ ハンド勝率（{hand_eq*100:.1f}%）またはレンジ勝率（{range_eq*100:.1f}%）が不足しています。先攻（OOP）の不利を補うため、レンジ全体でチェック頻度を高め、防衛ラインに回るべき局面です。")
                        st.rerun()
            else:
                if choice in [1, 2]:
                    # ベット成功時のルート
                    if st.button("相手のアクションを見る ➡️", use_container_width=True, key=f"btn_go_v1_{street}"):
                        bet_size = data["pot"] * (0.33 if choice == 1 else 0.70)
                        data["pot"] += (bet_size * 2)
                        data["street_history"][street] = "bet"
                        st.session_state.quiz_answered = False
                        st.session_state.quiz_phase = "next_street_trigger"
                        st.rerun()
                else:
                    # チェックを選択して正解した後のルート
                    if st.button("チェック後に相手の対抗ベットを受ける ➡️", use_container_width=True, key=f"btn_go_v_bet_{street}"):
                        data["oop_action_taken"] = "check"
                        st.session_state.quiz_phase = 2
                        st.session_state.quiz_answered = False
                        st.rerun()
                        
        elif st.session_state.quiz_phase == 2:
            villain_bet_size = 0.75 if (barrel_count >= 1 or hand_eq >= 0.85) else 0.66
            st.warning(f"🤖 【相手({data['villain_pos']})のアクション】")
            st.write(f"あなたのチェックを受けて、相手はポットの {int(villain_bet_size*100)}% サイズで【ベット】してきました！")
            st.markdown("### 【相手のベットに対するあなたの決断は？】")
            
            if street == "flop": best_def = 3 if hand_eq >= 0.75 else (2 if hand_eq >= 0.42 else 1)
            elif street == "turn": best_def = 3 if hand_eq >= 0.78 else (2 if hand_eq >= 0.50 else 1)
            elif street == "river": best_def = 3 if hand_eq >= 0.82 else (2 if hand_eq >= 0.58 else 1)
            
            def_options = ["1: フォールドする", "2: コールする", "3: レイズを返す"]
            ans2 = st.radio("👉 番号を選択してください (1-3):", def_options, key=f"oop_p2_{street}")
            choice2 = int(ans2[0])
            
            if not st.session_state.quiz_answered:
                if st.button("決断を確定する 🤝", use_container_width=True, key=f"btn_oop_p2_{street}"):
                    if choice2 != best_def:
                        if hand_eq >= 0.85:
                            st.error("❌ 不正解！ここでコール（2番）を返すだけでは、せっかく誘い出した相手のスタック（残りのチップ）を全額お仕置きする機会を逃してしまいます（バリューの損失）。最強の手だからこそ、やるべきことは一つです！")
                        else:
                            st.error("❌ 不正解！相手のバレル頻度と、自分のハンドがただの『ブラフキャッチャー』に過ぎない点を考慮してください。")
                    else:
                        st.session_state.quiz_answered = True
                        st.success("✨ 🎉 【大正解！】")
                        st.markdown("### 💡 【GTOディフェンス解説 (OOP / {})】".format(street.upper()))
                        if best_def == 3:
                            if hand_eq >= 0.85:
                                st.info(f"➔ 【チェックレイズ成功・全チップ回収】罠が完璧に決まりました！勝率 {hand_eq*100:.1f}% のナッツフルハウスを隠し持った状態から、相手の75%ベットに対して特大のレイズ（オールイン要求など）を返します。相手は自ら大きく賭けてしまったため、引くに引けず致命的な大損害を被ることになります。期待値(EV)最高のアクションです。")
                            else:
                                st.info(f"➔ ハンド勝率が {hand_eq*100:.1f}% と非常に高く、相手のライトバレル（ブラフ）を粉砕しつつ、バリューを最大化するためにチェックレイズを返すのが最適です。")
                        elif best_def == 2:
                            st.info(f"➔ 相手のベットサイズに対する必要勝率（オッズ）を、あなたのハンド勝率（{hand_eq*100:.1f}%）が上回っています。強い手には負けている可能性がありますが、相手のブラフをキャッチ（利確）するためにコールが義務付けられる『ブラフキャッチャー』の領域です。")
                        elif best_def == 1:
                            st.info(f"➔ 相手はストリートを連続して打ってきており、レンジがバリューに偏っています。あなたのハンド勝率（{hand_eq*100:.1f}%）ではポットオッズが合わないため、未練なくフォールドするのが長期的なEVを最大化します。")
                        st.rerun()
            else:
                if st.button("次のステップへ進む ➡️", use_container_width=True, key=f"btn_oop_p2_end_{street}"):
                    if choice2 == 2: data["pot"] += (data["pot"] * villain_bet_size * 2)
                    elif choice2 == 3: data["pot"] += (data["pot"] * villain_bet_size * 4)
                    data["street_history"][street] = "villain_bet"
                    st.session_state.quiz_answered = False
                    st.session_state.quiz_phase = "next_street_trigger"
                    st.rerun()

    # --- パターンB: 【後攻(IP)】の処理群 ---
    else:
        villain_bets = range_eq < 0.44 and street != "river"
        
        if villain_bets:
            st.warning(f"🤖 【相手({data['villain_pos']})のアクション】ポットの66%サイズで【ベット】してきました！")
            st.markdown("### 【ベットされたあなた(IP)のアクションは？】")
            
            if hand_eq >= 0.75: best_ip_def = 3
            elif hand_eq >= 0.44: best_ip_def = 2
            else: best_ip_def = 1
            
            ip_def_opts = ["1: フォールドする", "2: コールする", "3: レイズを返す"]
            ans_ip1 = st.radio("👉 番号を選択してください (1-3):", ip_def_opts, key=f"ip_p1_bet_{street}")
            choice = int(ans_ip1[0])
            
            if not st.session_state.quiz_answered:
                if st.button("決断を確定する 🤝", use_container_width=True, key=f"btn_ip_p1_{street}"):
                    if choice != best_ip_def:
                        st.error("❌ 不正解！必要エキティが不足しているか、バリューレイズの機会を逃しています。")
                    else:
                        st.session_state.quiz_answered = True
                        st.success("✨ 🎉 【大正解！】")
                        st.markdown("### 💡 【GTOディフェンス解説 (IP / {})】".format(street.upper()))
                        if best_ip_def == 3: st.info(f"➔ 後攻（IP）の有利さを活かし、勝率 {hand_eq*100:.1f}% のモンスターハンドで即座にレイズを返し、ポットを爆発させるべきです。")
                        elif best_ip_def == 2: st.info(f"➔ 後攻（IP）であるため、コールするだけで次のストリートも相手の出方を見られるポジション優位があります。")
                        elif best_ip_def == 1: st.info(f"➔ 相手の先攻ベットに対し、あなたのハンド勝率（{hand_eq*100:.1f}%）はオッズに見合いません。")
                        st.rerun()
            else:
                if st.button("次のステップへ進む ➡️", use_container_width=True, key=f"btn_ip_p1_end_{street}"):
                    if choice == 2: data["pot"] += (data["pot"] * 0.66 * 2)
                    elif choice == 3: data["pot"] += (data["pot"] * 0.66 * 4)
                    data["street_history"][street] = "bet"
                    st.session_state.quiz_answered = False
                    st.session_state.quiz_phase = "next_street_trigger"
                    st.rerun()
                    
        else:
            st.success(f"🤖 【相手({data['villain_pos']})のアクション】: 💤 【チェック】してきました。")
            st.markdown("### 【チェックで回ってきたあなた(IP)のアクションは？】")
            
            if street == "river":
                best_ip_act = 2 if hand_eq >= 0.66 else (1 if (hand_eq < 0.28 and range_eq >= 0.52) else 3)
            else:
                if hand_eq >= 0.64: best_ip_act = 2
                elif hand_eq >= 0.54: best_ip_act = 1
                elif hand_eq < 0.32 and range_eq >= 0.50: best_ip_act = 1
                else: best_ip_act = 3
                
            ip_check_opts = ["1: 小さくベットを打つ (ポットの33%)", "2: 大きくベットを打つ (ポットの66%〜75%)", "3: チェックバックする"]
            ans_ip2 = st.radio("👉 番号を選択してください (1-3):", ip_check_opts, key=f"ip_p2_check_{street}")
            choice = int(ans_ip2[0])
            
            if not st.session_state.quiz_answered:
                if st.button("決断を確定する 🤝", use_container_width=True, key=f"btn_ip_p2_{street}"):
                    if choice != best_ip_act:
                        st.error("❌ 不正解！『ベットして自分より弱い手がコールしてくれるか？』を深く考えてください。")
                    else:
                        st.session_state.quiz_answered = True
                        st.success("✨ 🎉 【大正解！】")
                        st.markdown("### 💡 【GTOアクション解説 (IP / {})】".format(street.upper()))
                        if best_ip_act == 2: st.info(f"➔ 相手のチェックにより弱みが露呈しました。あなたの勝率 {hand_eq*100:.1f}% は明確なバリュー領域です。ポットを大きく膨らませて利益を最大化してください。")
                        elif best_ip_act == 1:
                            if hand_eq >= 0.54: st.info(f"➔ マージナルバリュー（薄いバリュー）です。小さなベットを打つことで、相手の『あなたよりさらに弱い手』からコールを引き出しつつ、プロテクション効果を最大化します。")
                            else: st.info(f"➔ あなたのハンドは最弱（勝率 {hand_eq*100:.1f}%）ですが、レンジ全体（{range_eq*100:.1f}%）は有利です。『ピュアブラフベット』の局面です。")
                        elif best_ip_act == 3:
                            if street == "river": st.info(f"➔ 【超重要】リバーにおいて、あなたのハンド勝率（{hand_eq*100:.1f}%）は『ショーダウンバリュー（SDV）』の塊です。チェックバックを選択して安全に利確を掴み取るのがGTOの絶対原則です。")
                            else: st.info(f"➔ 中途半端な強さ（勝率 {hand_eq*100:.1f}%）のハンドです。チェックバックを選択して無料で次のカードを見にいくのが最善です。")
                        st.rerun()
            else:
                if st.button("次のステップへ進む ➡️", use_container_width=True, key=f"btn_ip_p2_end_{street}"):
                    action_taken = "check"
                    if choice in [1, 2]:
                        action_taken = "bet"
                        bet_size = data["pot"] * (0.33 if choice == 1 else 0.70)
                        data["pot"] += (bet_size * 2)
                    data["street_history"][street] = action_taken
                    st.session_state.quiz_answered = False
                    st.session_state.quiz_phase = "next_street_trigger"
                    st.rerun()

    # --- 各ストリート終了後の進級トリガー ---
    if st.session_state.quiz_phase == "next_street_trigger":
        if street == "flop":
            data["current_street"] = "turn"
            st.session_state.quiz_phase = 1
            st.rerun()
        elif street == "turn":
            data["current_street"] = "river"
            st.session_state.quiz_phase = 1
            st.rerun()
        else:
            st.balloons()
            st.subheader(f"🏆 リバーまで終了しました！ 最終ポット総額: {data['pot']:.1f}bb")
            if st.button("次のゲーム（特訓）へ進む 🔄", use_container_width=True, key="btn_next_game"):
                st.session_state.game_state = "setup"
                st.rerun()
