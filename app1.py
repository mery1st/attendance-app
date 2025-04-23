from flask import Flask, render_template_string, request, redirect, jsonify, url_for
import csv
import os
import secrets
from datetime import datetime

app = Flask(__name__)

EVENTS_FILE = "events.csv"
get_csv_file = lambda eid: f"responses_{eid}.csv"
get_dates_file = lambda eid: f"dates_{eid}.txt"
get_order_file = lambda eid: f"order_{eid}.txt"

def get_event_name(event_id):
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, newline='', encoding='utf-8') as f:
            for row in csv.reader(f):
                if row[0] == event_id:
                    return row[1]
    return None

@app.route("/")
def index():
    return render_template_string("""
    <h1>📋 新しいイベントを作成</h1>
    <form action="/create" method="post">
      イベント名（日本語OK）: <input name="event_name">
      <input type="submit" value="作成">
    </form>
    """)

@app.route("/create", methods=["POST"])
def create_event():
    event_name = request.form["event_name"].strip()
    event_id = secrets.token_hex(4)
    with open(EVENTS_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([event_id, event_name])
    with open(get_csv_file(event_id), "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["名前", "コメント", "コメント日時"])
    open(get_dates_file(event_id), "w", encoding="utf-8").close()
    return redirect(url_for("host_view", event_id=event_id))

@app.route("/host/<event_id>", methods=["GET", "POST"])
def host_view(event_id):
    return render_event(event_id, host=True)

@app.route("/event/<event_id>")
def member_view(event_id):
    return render_event(event_id, host=False)

@app.route("/host/<event_id>/sort")
def sort_names(event_id):
    csv_file = get_csv_file(event_id)
    if not os.path.exists(csv_file):
        return "イベントが存在しません"
    with open(csv_file, newline="", encoding="utf-8") as f:
        responses = list(csv.DictReader(f))
    names = [r["名前"] for r in responses]
    return render_template_string(sort_template, names=names, event_id=event_id)

@app.route("/host/<event_id>/reorder", methods=["POST"])
def save_order(event_id):
    data = request.get_json()
    order = data.get("order", [])
    with open(get_order_file(event_id), "w", encoding="utf-8") as f:
        f.write("\n".join(order))
    return jsonify({"redirect": url_for("host_view", event_id=event_id)})

@app.route("/edit/<event_id>/<name>", methods=["GET", "POST"])
def edit(event_id, name):
    csv_file, date_file = get_csv_file(event_id), get_dates_file(event_id)
    with open(date_file, encoding="utf-8") as f:
        dates = [line.strip() for line in f if line.strip()]
    with open(csv_file, newline="", encoding="utf-8") as f:
        responses = list(csv.DictReader(f))

    index = next((i for i, r in enumerate(responses) if r["名前"] == name), None)
    user = responses[index] if index is not None else None

    if request.method == "POST":
        new_row = {
            "名前": request.form["name"].strip(),
            "コメント": request.form.get("comment", ""),
            "コメント日時": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        for d in dates:
            new_row[d] = request.form.get(d, "×")
            new_row[d + "_reason"] = request.form.get(d + "_reason", "")
        if index is not None:
            responses[index] = new_row
        else:
            responses.append(new_row)
        fieldnames = ["名前", "コメント", "コメント日時"] + [x for d in dates for x in (d, d + "_reason")]
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in responses:
                writer.writerow(row)
        return redirect(url_for("member_view", event_id=event_id))

    return render_template_string(edit_template, name=name, user=user, dates=dates, event_id=event_id)

def render_event(event_id, host):
    event_name = get_event_name(event_id)
    csv_file = get_csv_file(event_id)
    date_file = get_dates_file(event_id)
    order_file = get_order_file(event_id)

    if not os.path.exists(csv_file) or not os.path.exists(date_file):
        return "イベントが存在しません"

    if request.method == "POST" and host:
        if "new_date" in request.form:
            with open(date_file, "a", encoding="utf-8") as f:
                f.write(request.form["new_date"].strip() + "\n")
        elif "delete_date" in request.form:
            del_date = request.form["delete_date"]
            with open(date_file, encoding="utf-8") as f:
                dates = [d for d in f.read().splitlines() if d != del_date]
            with open(date_file, "w", encoding="utf-8") as f:
                f.write("\n".join(dates) + "\n")
            with open(csv_file, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            for r in rows:
                r.pop(del_date, None)
                r.pop(del_date + "_reason", None)
            fieldnames = ["名前", "コメント", "コメント日時"] + [d for date in dates for d in (date, date + "_reason")]
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)
        return redirect(url_for("host_view", event_id=event_id))

    with open(date_file, encoding="utf-8") as f:
        dates = [line.strip() for line in f if line.strip()]
    with open(csv_file, newline="", encoding="utf-8") as f:
        responses = list(csv.DictReader(f))

    names = [r["名前"] for r in responses]
    if os.path.exists(order_file):
        with open(order_file, encoding="utf-8") as f:
            ordered = [line.strip() for line in f if line.strip()]
            names = [n for n in ordered if n in names] + [n for n in names if n not in ordered]

    table_data = {d: {} for d in dates}
    for r in responses:
        for d in dates:
            table_data[d][r["名前"]] = r.get(d, "")

    reason_lookup = {(d, r["名前"]): r.get(d + "_reason", "") for r in responses for d in dates}
    comments = sorted([
        {"name": r["名前"], "comment": r["コメント"], "time": r["コメント日時"]}
        for r in responses if r["コメント"].strip()
    ], key=lambda x: x["time"], reverse=True)

    counts = {d: {"◯": 0, "△": 0, "×": 0} for d in dates}
    for d in dates:
        for name in names:
            val = table_data[d].get(name, '')
            if val in counts[d]:
                counts[d][val] += 1

    return render_template_string(main_template, **locals())


# HTMLテンプレートは省略し、次に貼り付ける形式とします。
sort_template = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>参加者の並び替え</title>
  <style>
    #sortable {
      list-style: none;
      padding: 0;
      width: 300px;
    }
    #sortable li {
      padding: 10px;
      margin: 4px 0;
      background: #f0f0f0;
      border: 1px solid #ccc;
      cursor: move;
    }
    button {
      margin-top: 10px;
    }
  </style>
</head>
<body>
<h1>👥 参加者の並び替え（ドラッグ＆ドロップ）</h1>
<ul id="sortable">
  {% for name in names %}
    <li data-name="{{ name }}">{{ name }}</li>
  {% endfor %}
</ul>
<button onclick="saveOrder()">💾 並び順を保存</button>

<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script src="https://code.jquery.com/ui/1.13.2/jquery-ui.min.js"></script>
<script>
  $(function() {
    $("#sortable").sortable();
    $("#sortable").disableSelection();
  });

  function saveOrder() {
    const order = [];
    document.querySelectorAll('#sortable li').forEach(li => {
      order.push(li.dataset.name);
    });

    fetch("/host/{{ event_id }}/reorder", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ order: order })
    }).then(response => {
      if (response.ok) alert("並び順を保存しました！");
      else alert("保存に失敗しました");
    });
  }
</script>
<script>
  $(function() {
    $("#sortable").sortable();
    $("#sortable").disableSelection();
  });

  function saveOrder() {
    const order = [];
    document.querySelectorAll('#sortable li').forEach(li => {
      order.push(li.dataset.name);
    });

    fetch("/host/{{ event_id }}/reorder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order: order })
    }).then(response => response.json())
      .then(data => {
        if (data.redirect) {
          window.location.href = data.redirect; // 自動的にリダイレクト
        } else {
          alert("保存に失敗しました");
        }
      });
  }
</script>
</body>
</html>
"""
main_template = """
<!doctype html><title>{{ event_name }}</title>
<style>
  table { border-collapse: collapse; }
  th, td { padding: 6px 10px; text-align: center; }
  .mark { font-weight: bold; padding: 5px; border-radius: 4px; display: inline-block; width: 2em; }
  .mark-◯ { background-color: #c8facc; }
  .mark-△ { background-color: #fff7b3; }
  .mark-× { background-color: #ffcaca; }
  .date-title { text-align: left; white-space: nowrap; }
</style>
<h1>{{ event_name }}</h1>
{% if host %}
<h3>📎 メンバー用URL: 
  <input type="text" id="memberLink" value="http://127.0.0.1:5000/event/{{ event_id }}" readonly size="40">
  <button onclick="copyLink()">コピー</button>
</h3>
<a href="/host/{{ event_id }}/sort">👥 並び替え画面へ</a><br><br>
<script>
function copyLink() {
  const input = document.getElementById("memberLink");
  input.select();
  input.setSelectionRange(0, 99999);
  document.execCommand("copy");
  alert("メンバー用URLをコピーしました！");
}
</script>
{% endif %}

{% if host %}
<form method="post">
  <input name="new_date" placeholder="日付を追加">
  <button type="submit">追加</button>
</form>
{% endif %}

<table border="1">
<tr><th>日付＼名前</th>{% for name in names %}<th><a href="/edit/{{ event_id }}/{{ name }}">{{ name }}</a></th>{% endfor %}</tr>
{% for d in dates %}
<tr>
  <td class="date-title">
    {{ d }}（◯{{ counts[d]['◯'] }} △{{ counts[d]['△'] }} ×{{ counts[d]['×'] }}）
    {% if host %}
    <form method="post" style="display:inline;"><input type="hidden" name="delete_date" value="{{ d }}"><button type="submit">🗑</button></form>
    {% endif %}
  </td>
  {% for name in names %}
    {% set val = table_data[d].get(name, '') %}
    {% set reason = reason_lookup.get((d, name), '') %}
    <td>
      {% if val in ['◯', '△', '×'] %}
        {% set cls = 'mark-' + val %}
        <span class="mark {{ cls }}" title="{{ reason }}">{{ val }}</span>
      {% else %}
        {{ val }}
      {% endif %}
    </td>
  {% endfor %}
</tr>
{% endfor %}
</table>

<h2>【コメント】</h2>
<ul>{% for c in comments %}<li>（<b>{{ c.name }}</b>）{{ c.comment }}［{{ c.time }}］</li>{% else %}<li>コメントはまだありません。</li>{% endfor %}</ul>
<a href="/edit/{{ event_id }}/あなたの名前">＋ 出欠を入力・編集する</a>
"""
edit_template = """
<!doctype html><title>{{ name }} さんの出席編集</title>
<h1>{{ name }} さんの出席編集</h1>
<form method="post">
名前: <input name="name" value="{{ user['名前'] if user else name }}"><br><br>
コメント: <input name="comment" value="{{ user['コメント'] if user else '' }}"><br><br>
{% for d in dates %}
<label>{{ d }}:
  <select name="{{ d }}">
    <option value="◯" {% if user and user[d] == '◯' %}selected{% endif %}>◯</option>
    <option value="△" {% if user and user[d] == '△' %}selected{% endif %}>△</option>
    <option value="×" {% if user and user[d] == '×' %}selected{% endif %}>×</option>
  </select>
  <input type="text" name="{{ d }}_reason" placeholder="理由" id="reason_{{ d }}" value="{{ user[d + '_reason'] if user and d + '_reason' in user else '' }}" style="display:none;">
</label><br>
{% endfor %}
<input type="submit" value="保存">
</form>

<a href="/event/{{ event_id }}">← 出欠表に戻る</a>

<script>
function toggleReason(select, date) {
  const input = document.getElementById("reason_" + date);
  if (!input) return;
  input.style.display = (select.value === "△" || select.value === "×") ? "inline" : "none";
}

// 初期状態と変更時の理由欄の表示制御
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("select").forEach(select => {
    toggleReason(select, select.name);
    select.addEventListener("change", function () {
      toggleReason(this, this.name);
    });
  });
});
</script>
"""
if __name__ == "__main__":
    app.run(debug=True)






















