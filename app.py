import streamlit as st
import random
import pandas as pd
import eval7

# ページの設定（スマホで見やすいようにワイドモードにする）
st.set_page_config(page_title="GTO特訓ツール", page_icon="🃏", layout="centered")

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
def load_ranges():
    try:
        df = pd.read_csv("poker_range_list.csv")
        return dict(zip(df['hand'], df['color']))
    except:
        # ファイルがない場合のフォールバック用テストデータ
        return {"AA": "紺", "AKo": "赤", "AQs": "赤", "AhJh": "黄", "KhQh": "緑", "76s": "水色"}

def convert_to_concrete_cards(hand_str):
    ranks = "23456789TJQKA"
    suits = "shcd"
    if len(hand_str) < 2: return []
    r1, r2 = hand_str[0], hand_str[1]
    is_suited, is_offsuit = hand_str.endswith('s'), hand_str.endswith('o')
    combos = []
    if r1 == r2:
        for i in range(4):
            for j in range(i + 1, 4): combos.append([r1 + suits[i], r2 + suits[j]])
    elif is_suited:
        for s in suits: combos.append([r1 + s, r2 + s])
    else:
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
    if villain_pos == "BB": return ALL_COLORS[max(0, ALL_COLORS.index(hero_open_colors[-1]) - 1):]
    if villain_pos == "SB": return ALL_COLORS[ALL_COLORS.index(hero_open_colors[-1]):]
    return ALL_COLORS[min(len(ALL_COLORS) - 1, ALL_COLORS.index(hero_open_colors[-1]) + 1):]

def run_simulation(hero_combos, villain_combos, board):
    if not hero_combos or not villain_combos: return 0.5
    hero_wins, villain_wins, ties = 0, 0, 0
    deck_base = [eval7.Card(f"{r}{s}") for r in "23456789TJQKA" for s in "shcd"]
    for _ in range(500): # スマホ用に計算を軽量化
        h_cards_raw = random.choice(hero_combos)
        v_cards_raw = random.choice(villain_combos)
        h_cards = [eval7.Card(c) for c in h_cards_raw]
        v_cards = [eval7.Card(c) for c in v_cards_raw]
        used_cards = set(h_cards + v_cards + board)
        if len(used_cards) != len(h_cards) + len(v_cards) + len(board): continue
        remaining_deck = [c for c in deck_base if c not in used_cards]
        num_to_draw = 5 - len(board)
        interim_board = board + random.sample(remaining_deck, num_to_draw) if num_to_draw > 0 else board
        hero_score = eval7.evaluate(h_cards + interim_board)
        villain_score = eval7.evaluate(v_cards + interim_board)
        if hero_score > villain_score: hero_wins += 1
        elif villain_score > hero_score: villain_wins += 1
        else: ties += 1
    return (hero_wins + 0.5 * ties) / (hero_wins + villain_wins + ties) if (hero_wins + villain_wins + ties) > 0 else 0.5

def is_hero_oop(hero_pos, villain_pos):
    order = ["SB", "BB", "UTG", "HJ", "CO", "BTN"]
    return order.index(hero_pos) < order.index(villain_pos)

# --- 状態管理の初期化 ---
if "game_state" not in st.session_state:
    st.session_state.game_state = "setup" # setup, flop, turn, river, finished

hand_to_color = load_ranges()

st.title("🃏 GTOクイズ特訓アプリ")

if st.session_state.game_state == "setup":
    st.subheader("🛠️ トレーニング設定")
    pos_choice = st.selectbox("自分のポジション(Hero)を選択してください:", ["ランダム"] + POSITIONS_LIST)
    
    if st.button("ゲームに挑む 🚀", use_container_width=True):
        hero_pos = random.choice(POSITIONS_LIST) if pos_choice == "ランダム" else pos_choice
        villain_pos = random.choice([p for p in POSITIONS_LIST if p != hero_pos])
        
        allowed_colors = POSITION_RULES[hero_pos]["open"]
        available_hands = [h for h, c in hand_to_color.items() if c in allowed_colors]
        if not available_hands: available_hands = list(hand_to_color.keys())
        chosen_hand = random.choice(available_hands)
        hero_hand_pair = random.choice(convert_to_concrete_cards(chosen_hand))
        
        deck = [f"{r}{s}" for r in "23456789TJQKA" for s in "shcd" if f"{r}{s}" not in hero_hand_pair]
        random.shuffle(deck)
        
        st.session_state.game_data = {
            "hero_pos": hero_pos,
            "villain_pos": villain_pos,
            "hero_hand": f"{hero_hand_pair[0]}{hero_hand_pair[1]}",
            "hero_color": hand_to_color.get(chosen_hand, "不明"),
            "villain_colors": determine_dynamic_ranges(hero_pos, villain_pos),
            "deck": deck,
            "board": [],
            "pot": 5.5,
            "history": []
        }
        st.session_state.game_state = "flop"
        st.rerun()

else:
    data = st.session_state.game_data
    street = st.session_state.game_state
    
    # 新しいカードの配布
    if street == "flop" and len(data["board"]) == 0:
        data["board"] = [data["deck"].pop() for _ in range(3)]
    elif street == "turn" and len(data["board"]) == 3:
        data["board"].append(data["deck"].pop())
    elif street == "river" and len(data["board"]) == 4:
        data["board"].append(data["deck"].pop())

    # ステータス表示
    st.markdown(f"### ⚔️ シチュエーション: **{street.upper()}**")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("あなた (Hero)", f"{data['hero_pos']} (OOP)" if is_hero_oop(data['hero_pos'], data['villain_pos']) else f"{data['hero_pos']} (IP)")
        st.markdown(f"**手札**: `{data['hero_hand']}` (【{data['hero_color']}】)")
    with col2:
        st.metric("相手 (Villain)", data['villain_pos'])
        st.markdown(f"**敵レンジ**: {', '.join(data['villain_colors'])}")
        
    st.info(f"📁 **現在のボード**: `{' '.join(data['board'])}`  |  💰 **ポット**: {data['pot']:.1f}bb")

    # 勝率の計算
    hero_single_combo = [[data['hero_hand'][0:2], data['hero_hand'][2:4]]]
    villain_range_combos = get_range_combos(data['villain_colors'], hand_to_color)
    board_obj = [eval7.Card(c) for c in data['board']]
    
    hand_eq = run_simulation(hero_single_combo, villain_range_combos, board_obj)
    
    st.caption(f"📊 あなたの現在のハンド勝率: **{hand_eq*100:.1f}%**")

    # OOP先攻アクションフェーズ
    hero_oop = is_hero_oop(data['hero_pos'], data['villain_pos'])
    
    if "quiz_answered" not in st.session_state:
        st.session_state.quiz_answered = False

    if not st.session_state.quiz_answered:
        st.write("#### 👉 あなたのアクションを決めてください:")
        
        # 正解ロジック（簡易判定）
        if hand_eq >= 0.85:
            best_action = 3 if street == "river" else 1
        elif hand_eq >= 0.65:
            best_action = 2
        elif hand_eq >= 0.50:
            best_action = 1
        else:
            best_action = 3
            
        ans = st.radio("選択肢:", ["1: 小さくベットする (ポットの33%)", "2: 大きくベットする (ポットの75%)", "3: チェックする"], index=0)
        user_choice = int(ans[0])
        
        if st.button("決断を確定する 🤝", use_container_width=True):
            st.session_state.quiz_answered = True
            st.session_state.is_correct = (user_choice == best_action)
            st.session_state.user_choice = user_choice
            st.rerun()
            
    else:
        # クイズ結果の発表
        if st.session_state.is_correct:
            st.success("✨ 【正解です！】")
        else:
            st.error("❌ 【不正解です！】最適戦略ではありません。")
            
        # 解説文の表示
        if st.session_state.user_choice == 3 and hand_eq >= 0.85:
            st.markdown("💡 **GTO解説**: 【至高のトラップ】圧倒的モンスターハンドです。ベットすると相手を逃がしてしまうため、チェックで相手のブラフや薄いバリューベットを強烈に誘い出す（インデュース）のがGTO最高EVになります。")
        elif hand_eq >= 0.85:
            st.markdown("💡 **GTO解説**: 【バリューの最大化】圧倒的な勝率を誇るモンスターハンドです。しっかりベットを打ってポットを大きく構築していきましょう。")
        else:
            st.markdown(f"💡 **GTO解説**: ハンド勝率が {hand_eq*100:.1f}% の局面での標準的なマッピングアクションです。")

        # 相手のアクションシミュレートとポットの更新
        if st.button("次のストリートへ進む ➡️", use_container_width=True):
            st.session_state.quiz_answered = False
            if street == "flop":
                data["pot"] += 4.0 # ダミーのベット・コール分
                st.session_state.game_state = "turn"
            elif street == "turn":
                data["pot"] += 10.0
                st.session_state.game_state = "river"
            else:
                st.balloons()
                st.session_state.game_state = "setup"
            st.rerun()
