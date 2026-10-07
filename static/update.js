/* The Update button (templates/_nav.html). It shows only when a newer MyVocab
   release is out: updates.py asks GitHub about every half hour, and this page
   asks the app as often. "Update now" starts tools/update.py through run.py,
   then this follows its progress, waits while MyVocab restarts, and reloads
   on the new version. On Vercel and in a developer's clone it stays hidden. */
(() => {
    const box = document.getElementById("update-box");
    if (!box) return;
    const $ = (id) => document.getElementById(id);
    const CHECK_EVERY = 30 * 60 * 1000;
    const STEP_PERCENT = { waiting: 6, download: 22, backup: 45, restart: 65, start: 85, done: 100 };
    const FOLLOWING_KEY = "myvocab-update-following";  // survives a reload in the middle of an update
    const DONE_KEY = "myvocab-update-done";
    let latest = null;
    let following = false;

    const session = {
        get(key) { try { return sessionStorage.getItem(key); } catch (e) { return null; } },
        set(key, value) { try { sessionStorage.setItem(key, value); } catch (e) { /* private window */ } },
        clear(key) { try { sessionStorage.removeItem(key); } catch (e) { /* private window */ } },
    };
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

    function getStatus() {
        return fetch("/api/update/status", { cache: "no-store" }).then((r) => {
            if (!r.ok) throw new Error(r.status);
            return r.json();
        });
    }

    function openPanel(open) {
        $("update-panel").hidden = !open;
        $("update-button").setAttribute("aria-expanded", String(open));
    }

    // Release notes are plain text from GitHub: "- " lines become a list. Never parsed as HTML.
    function showNotes(release) {
        $("update-title").textContent = `MyVocab ${release.tag} is ready`;
        const notes = $("update-notes");
        notes.replaceChildren();
        const lines = (release.notes || "").split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith("#"));
        const bullets = lines.filter((l) => /^[-*] /.test(l)).map((l) => l.slice(2));
        const items = (bullets.length ? bullets : lines).slice(0, 8).map((l) => l.replace(/\*\*|`/g, ""));
        if (!items.length) return;
        const heading = document.createElement("p");
        heading.className = "update-whats-new";
        heading.textContent = "What's new:";
        const list = document.createElement("ul");
        for (const text of items) {
            const li = document.createElement("li");
            li.textContent = text;
            list.append(li);
        }
        notes.append(heading, list);
    }

    function setProgress(step, message, kind) {
        $("update-progress").hidden = false;
        $("update-bar-fill").style.width = (STEP_PERCENT[step] ?? 10) + "%";
        const line = $("update-message");
        line.textContent = message;
        line.className = "update-message" + (kind ? " " + kind : "");
    }

    function busy(on) {
        box.classList.toggle("busy", on);
        $("update-now").hidden = on;
        $("update-later").hidden = on;
        $("update-button-label").textContent = on ? "Updating …" : "Update";
    }

    function fail(message) {
        following = false;
        session.clear(FOLLOWING_KEY);
        busy(false);
        $("update-now").textContent = "Try again";
        setProgress("waiting", message, "error");
        $("update-bar-fill").style.width = "0";
        openPanel(true);
    }

    function finish(tag) {
        session.clear(FOLLOWING_KEY);
        session.set(DONE_KEY, tag);
        setProgress("done", `Updated to ${tag}. Reloading …`, "ok");
        setTimeout(() => location.reload(), 1200);
    }

    async function follow(tag) {
        following = true;
        session.set(FOLLOWING_KEY, tag);
        box.hidden = false;
        busy(true);
        openPanel(true);
        if (!$("update-message").textContent) setProgress("waiting", "Starting the update …");
        const started = Date.now();
        let away = 0;
        for (;;) {
            await sleep(1500);
            let state = null;
            try {
                state = await getStatus();
                away = 0;
            } catch (e) {
                away += 1;
            }
            if (!state) {
                // MyVocab is closed while the new files go in, then starts again.
                setProgress("start", "MyVocab is restarting. This page reloads by itself …");
                if (away > 240) return fail("MyVocab did not come back. Open it with the MyVocab icon on your desktop.");
                continue;
            }
            const progress = state.progress;
            if (state.current === tag && (!progress || ["start", "done"].includes(progress.step))) return finish(tag);
            if (progress && progress.step === "error") return fail(progress.message);
            if (progress) setProgress(progress.step, progress.message);
            if ((!progress || progress.step === "waiting") && Date.now() - started > 25000) {
                return fail("The update did not start. Close MyVocab, open it again with its desktop icon, and try again.");
            }
        }
    }

    async function check() {
        if (following) return;
        let state;
        try {
            state = await getStatus();
        } catch (e) {
            return;  // offline, or MyVocab is restarting: ask again later
        }
        if (!state.enabled) return;
        const progress = state.progress;
        if (progress && !["done", "error"].includes(progress.step) && Date.now() / 1000 - progress.at < 900) {
            return follow(progress.tag);  // an update started from another tab
        }
        if (!state.available) {
            box.hidden = true;
            return;
        }
        latest = state.latest;
        showNotes(latest);
        box.hidden = false;
        if (progress && progress.step === "error" && progress.tag === latest.tag) {
            setProgress("waiting", progress.message, "error");
            $("update-bar-fill").style.width = "0";
            $("update-now").textContent = "Try again";
        }
    }

    $("update-button").addEventListener("click", () => openPanel($("update-panel").hidden));
    $("update-later").addEventListener("click", () => openPanel(false));
    $("update-now").addEventListener("click", async () => {
        if (!latest) return;
        $("update-now").disabled = true;
        try {
            const response = await fetch("/api/update/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ tag: latest.tag }),
            });
            const body = await response.json().catch(() => ({}));
            if (!response.ok) return fail(body.error || "The update could not start.");
            setProgress("waiting", "Starting the update …");
            follow(latest.tag);
        } catch (e) {
            fail("MyVocab is not answering. Is its window still open?");
        } finally {
            $("update-now").disabled = false;
        }
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !$("update-panel").hidden && !following) openPanel(false);
    });
    document.addEventListener("click", (event) => {
        if (!box.contains(event.target) && !$("update-panel").hidden && !following) openPanel(false);
    });

    // Just updated: say so for a few seconds.
    const done = session.get(DONE_KEY);
    if (done) {
        session.clear(DONE_KEY);
        box.hidden = false;
        box.classList.add("done");
        $("update-button-label").textContent = `Updated to ${done}`;
        $("update-button").querySelector("i").className = "fas fa-check-circle";
        window.MyVocabFx?.confetti();  // it stays still for reduced motion
        setTimeout(() => {
            box.hidden = true;
            box.classList.remove("done");
            $("update-button-label").textContent = "Update";
            $("update-button").querySelector("i").className = "fas fa-arrow-circle-up";
            check();
        }, 8000);
    } else if (session.get(FOLLOWING_KEY)) {
        follow(session.get(FOLLOWING_KEY));  // reloaded in the middle of an update
    } else {
        check();
    }
    setInterval(check, CHECK_EVERY);
})();
