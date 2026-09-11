(() => {
  const SOURCES = [
    { key: "all", label: "الكل" },
    { key: "exam1", label: "Exam 1" },
    { key: "exam2", label: "Exam 2" },
    { key: "exam3", label: "Exam 3" },
    { key: "max", label: "Practice Model" },
  ];

  const LETTERS = ["A", "B", "C", "D"];

  const els = {
    setupPanel: document.getElementById("setupPanel"),
    quizPanel: document.getElementById("quizPanel"),
    resultsPanel: document.getElementById("resultsPanel"),
    sourceChips: document.getElementById("sourceChips"),
    modeSelect: document.getElementById("modeSelect"),
    countSelect: document.getElementById("countSelect"),
    shuffleToggle: document.getElementById("shuffleToggle"),
    poolInfo: document.getElementById("poolInfo"),
    startBtn: document.getElementById("startBtn"),
    topStats: document.getElementById("topStats"),
    progressLabel: document.getElementById("progressLabel"),
    scoreLabel: document.getElementById("scoreLabel"),
    sourceBadge: document.getElementById("sourceBadge"),
    qCounter: document.getElementById("qCounter"),
    progressFill: document.getElementById("progressFill"),
    questionsList: document.getElementById("questionsList"),
    submitBtn: document.getElementById("submitBtn"),
    quitBtn: document.getElementById("quitBtn"),
    scoreRing: document.getElementById("scoreRing"),
    percentValue: document.getElementById("percentValue"),
    scoreDetail: document.getElementById("scoreDetail"),
    resultMsg: document.getElementById("resultMsg"),
    reviewList: document.getElementById("reviewList"),
    homeBtn: document.getElementById("homeBtn"),
    retryBtn: document.getElementById("retryBtn"),
    footerCount: document.getElementById("footerCount"),
  };

  const state = {
    source: "all",
    deck: [],
    answers: {}, // index -> choiceIndex
    mode: "practice",
    graded: false,
    lastConfig: null,
  };

  const allQuestions = Array.isArray(window.QUESTIONS) ? window.QUESTIONS : [];

  function shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function filteredPool() {
    if (state.source === "all") return allQuestions;
    return allQuestions.filter((q) => q.sourceKey === state.source);
  }

  function updatePoolInfo() {
    const n = filteredPool().length;
    const label = SOURCES.find((s) => s.key === state.source)?.label || "";
    els.poolInfo.textContent =
      n === 0
        ? "لا توجد أسئلة لهذا المصدر."
        : `متاح الآن: ${n} سؤالًا — ${label}`;
    els.startBtn.disabled = n === 0;
  }

  function renderChips() {
    els.sourceChips.innerHTML = "";
    SOURCES.forEach((s) => {
      const count =
        s.key === "all"
          ? allQuestions.length
          : allQuestions.filter((q) => q.sourceKey === s.key).length;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip" + (state.source === s.key ? " active" : "");
      btn.textContent = `${s.label} (${count})`;
      btn.addEventListener("click", () => {
        state.source = s.key;
        renderChips();
        updatePoolInfo();
      });
      els.sourceChips.appendChild(btn);
    });
  }

  function showPanel(name) {
    els.setupPanel.hidden = name !== "setup";
    els.quizPanel.hidden = name !== "quiz";
    els.resultsPanel.hidden = name !== "results";
    els.topStats.hidden = name !== "quiz";
  }

  function buildDeck() {
    const pool = filteredPool();
    const mode = els.modeSelect.value;
    const countVal = els.countSelect.value;
    let deck = els.shuffleToggle.checked ? shuffle(pool) : pool.slice();
    if (countVal !== "all") {
      deck = deck.slice(0, Math.min(Number(countVal), deck.length));
    }
    state.mode = mode;
    state.deck = deck;
    state.answers = {};
    state.graded = false;
    state.lastConfig = {
      source: state.source,
      mode,
      countVal,
      shuffle: els.shuffleToggle.checked,
    };
  }

  function answeredCount() {
    return Object.keys(state.answers).length;
  }

  function correctCount() {
    let n = 0;
    state.deck.forEach((q, i) => {
      if (state.answers[i] === q.answer) n += 1;
    });
    return n;
  }

  function updateHud() {
    const total = state.deck.length;
    const done = answeredCount();
    els.progressLabel.textContent = `${done} / ${total}`;
    els.scoreLabel.textContent = state.graded
      ? `صح: ${correctCount()}`
      : `مجاب: ${done}`;
    els.qCounter.textContent = `${total} سؤال في الصفحة`;
    els.progressFill.style.width = `${total ? (done / total) * 100 : 0}%`;
    els.submitBtn.textContent =
      state.mode === "practice" && !state.graded
        ? "تصحيح الإجابات"
        : state.graded
          ? "عرض النتيجة"
          : "إنهاء وتصحيح";
  }

  function renderAllQuestions() {
    els.questionsList.innerHTML = "";
    const sourceLabel =
      state.source === "all"
        ? "كل المصادر"
        : SOURCES.find((s) => s.key === state.source)?.label || "";
    els.sourceBadge.textContent = sourceLabel;

    state.deck.forEach((q, qi) => {
      const card = document.createElement("article");
      card.className = "q-card";
      card.dataset.index = String(qi);

      const head = document.createElement("div");
      head.className = "q-card-head";
      head.innerHTML = `
        <span class="q-num">${qi + 1}</span>
        <span class="q-src">${escapeHtml(q.source || "")}</span>`;

      const title = document.createElement("h2");
      title.className = "question";
      title.lang = "en";
      title.dir = "ltr";
      title.textContent = q.question;

      const choices = document.createElement("div");
      choices.className = "choices";
      choices.lang = "en";
      choices.dir = "ltr";

      q.choices.forEach((text, ci) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "choice";
        btn.dataset.choice = String(ci);
        btn.innerHTML = `<span class="key">${LETTERS[ci]}</span><span>${escapeHtml(
          text
        )}</span>`;
        btn.addEventListener("click", () => selectAnswer(qi, ci, card));
        choices.appendChild(btn);
      });

      const feedback = document.createElement("div");
      feedback.className = "feedback";
      feedback.hidden = true;

      card.append(head, title, choices, feedback);
      els.questionsList.appendChild(card);
    });

    updateHud();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function selectAnswer(qi, ci, card) {
    if (state.graded) return;

    state.answers[qi] = ci;
    const buttons = [...card.querySelectorAll(".choice")];
    buttons.forEach((b) => b.classList.remove("selected"));
    buttons[ci].classList.add("selected");

    // Practice: instant feedback per question, but stay on the list
    if (state.mode === "practice") {
      const q = state.deck[qi];
      const feedback = card.querySelector(".feedback");
      buttons.forEach((b) => {
        b.classList.remove("correct", "wrong");
        b.disabled = true;
      });
      buttons[q.answer].classList.add("correct");
      if (ci !== q.answer) buttons[ci].classList.add("wrong");
      feedback.hidden = false;
      if (ci === q.answer) {
        feedback.className = "feedback ok";
        feedback.textContent = "إجابة صحيحة ✓";
      } else {
        feedback.className = "feedback bad";
        feedback.textContent = `خطأ — الصحيح: ${LETTERS[q.answer]}. ${q.choices[q.answer]}`;
      }
    }

    updateHud();
  }

  function gradeAll() {
    state.graded = true;
    state.deck.forEach((q, qi) => {
      const card = els.questionsList.children[qi];
      if (!card) return;
      const picked = state.answers[qi];
      const buttons = [...card.querySelectorAll(".choice")];
      const feedback = card.querySelector(".feedback");
      buttons.forEach((b) => (b.disabled = true));

      buttons[q.answer].classList.add("correct");
      if (picked === undefined) {
        feedback.hidden = false;
        feedback.className = "feedback bad";
        feedback.textContent = `بدون إجابة — الصحيح: ${LETTERS[q.answer]}. ${q.choices[q.answer]}`;
        card.classList.add("missed");
      } else if (picked === q.answer) {
        feedback.hidden = false;
        feedback.className = "feedback ok";
        feedback.textContent = "إجابة صحيحة ✓";
        card.classList.add("ok");
      } else {
        buttons[picked].classList.add("wrong");
        feedback.hidden = false;
        feedback.className = "feedback bad";
        feedback.textContent = `خطأ — الصحيح: ${LETTERS[q.answer]}. ${q.choices[q.answer]}`;
        card.classList.add("bad");
      }
    });
    updateHud();
  }

  function finishQuiz() {
    if (!state.graded) gradeAll();

    const total = state.deck.length;
    const score = correctCount();
    const pct = total ? Math.round((score / total) * 100) : 0;
    showPanel("results");
    els.percentValue.textContent = `${pct}%`;
    els.scoreDetail.textContent = `${score} من ${total}`;
    els.scoreRing.style.setProperty("--p", `${pct}%`);

    let msg = "استمر في المراجعة — كل محاولة بتقوّيك.";
    if (pct >= 90) msg = "ممتاز! مستواك قوي جدًا.";
    else if (pct >= 70) msg = "جيد جدًا — راجع الأخطاء البسيطة.";
    else if (pct >= 50) msg = "نتيجة متوسطة — ركّز على المفردات الغلط.";
    els.resultMsg.textContent = msg;

    els.reviewList.innerHTML = "";
    state.deck.forEach((q, i) => {
      const picked = state.answers[i];
      const ok = picked === q.answer;
      const div = document.createElement("div");
      div.className = "review-item " + (ok ? "ok" : "bad");
      const pickedText =
        picked === undefined ? "بدون إجابة" : q.choices[picked];
      div.innerHTML = `
        <div class="q">${i + 1}. ${escapeHtml(q.question)}</div>
        <div class="a">${
          ok
            ? `✓ ${escapeHtml(q.choices[q.answer])}`
            : `اخترت: ${escapeHtml(pickedText)} · الصحيح: ${escapeHtml(
                q.choices[q.answer]
              )}`
        }</div>`;
      els.reviewList.appendChild(div);
    });

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function startQuiz() {
    if (!allQuestions.length) {
      els.poolInfo.textContent =
        "تعذر تحميل الأسئلة. تأكد من وجود ملف questions.js";
      return;
    }
    buildDeck();
    if (!state.deck.length) return;
    showPanel("quiz");
    renderAllQuestions();
  }

  function retry() {
    if (!state.lastConfig) {
      showPanel("setup");
      return;
    }
    const cfg = state.lastConfig;
    state.source = cfg.source;
    els.modeSelect.value = cfg.mode;
    els.countSelect.value = cfg.countVal;
    els.shuffleToggle.checked = cfg.shuffle;
    renderChips();
    updatePoolInfo();
    startQuiz();
  }

  if (!allQuestions.length) {
    els.poolInfo.textContent =
      "لم يتم العثور على أسئلة. شغّل extract_questions.py أولًا.";
    els.startBtn.disabled = true;
  } else {
    els.footerCount.textContent = `${allQuestions.length} سؤال محمّل من ملفات الامتحان`;
    renderChips();
    updatePoolInfo();
  }

  els.startBtn.addEventListener("click", startQuiz);
  els.submitBtn.addEventListener("click", () => {
    if (!state.graded) {
      gradeAll();
      // In exam mode, go straight to results after grading
      if (state.mode === "exam") finishQuiz();
      else {
        els.submitBtn.textContent = "عرض الملخص";
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    } else {
      finishQuiz();
    }
  });
  els.quitBtn.addEventListener("click", () => {
    showPanel("setup");
    updatePoolInfo();
  });
  els.homeBtn.addEventListener("click", () => {
    showPanel("setup");
    updatePoolInfo();
  });
  els.retryBtn.addEventListener("click", retry);
})();
