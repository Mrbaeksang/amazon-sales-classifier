import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from classifier import (
    Report,
    Row,
    classify,
    format_output1_tsv,
    format_output2_tsv,
    read_csv,
)
from master import (
    PROTECTED_CATEGORIES,
    add_category,
    add_eye_sub,
    category_in_use,
    delete_asin,
    delete_category,
    delete_eye_sub,
    eye_sub_in_use,
    load_master,
    master_path,
    rename_category,
    rename_eye_sub,
    reorder_category,
    reorder_eye_sub,
    save_master,
    upsert_asin,
)


APP_TITLE = "아마존 판매 자동분류"
EYE_PATCH_CAT = "아이세럼패치"
EYE_SUB_NONE = "(없음)"


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.master = load_master()
        self.report: Report | None = None
        self.current_csv: Path | None = None

        root.title(APP_TITLE)
        root.geometry("720x720")

        self._build_ui()
        self._refresh_outputs()

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        ttk.Button(top, text="📂 CSV 열기", command=self.open_csv).pack(side="left")
        ttk.Button(top, text="⚙ ASIN 편집", command=self.open_master_editor).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="📁 카테고리 관리", command=self.open_category_editor).pack(side="left", padx=(8, 0))
        self.file_label = ttk.Label(top, text="파일 없음", foreground="#666")
        self.file_label.pack(side="left", padx=(12, 0))

        sep1 = ttk.Separator(self.root)
        sep1.pack(fill="x", padx=10)

        out1_frame = ttk.LabelFrame(self.root, text="📊 출력1 — 전체 카테고리별", padding=8)
        out1_frame.pack(fill="both", expand=True, padx=10, pady=(8, 4))
        top1 = ttk.Frame(out1_frame)
        top1.pack(fill="x")
        ttk.Button(top1, text="📋 복사 (TSV)", command=self.copy_output1).pack(side="right")
        self.out1_tree = ttk.Treeview(out1_frame, columns=("rev",), show="tree headings", height=8)
        self.out1_tree.heading("#0", text="카테고리")
        self.out1_tree.heading("rev", text="매출")
        self.out1_tree.column("#0", width=200)
        self.out1_tree.column("rev", width=140, anchor="e")
        self.out1_tree.pack(fill="both", expand=True, pady=(6, 0))

        out2_frame = ttk.LabelFrame(self.root, text="🧊 출력2 — 아이패치 세부분류", padding=8)
        out2_frame.pack(fill="both", expand=True, padx=10, pady=(4, 4))
        top2 = ttk.Frame(out2_frame)
        top2.pack(fill="x")
        ttk.Button(top2, text="📋 복사 (TSV)", command=self.copy_output2).pack(side="right")
        self.out2_tree = ttk.Treeview(out2_frame, columns=("rev", "qty"), show="tree headings", height=4)
        self.out2_tree.heading("#0", text="세부분류")
        self.out2_tree.heading("rev", text="매출")
        self.out2_tree.heading("qty", text="수량")
        self.out2_tree.column("#0", width=160)
        self.out2_tree.column("rev", width=140, anchor="e")
        self.out2_tree.column("qty", width=80, anchor="e")
        self.out2_tree.pack(fill="both", expand=True, pady=(6, 0))

        status = ttk.Frame(self.root, padding=(10, 6))
        status.pack(fill="x")
        self.status_label = ttk.Label(status, text="CSV 파일을 열어주세요.", foreground="#555")
        self.status_label.pack(side="left")

    def open_csv(self):
        path = filedialog.askopenfilename(
            title="아마존 일별 판매 CSV 선택",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        self.current_csv = Path(path)
        self.file_label.config(text=self.current_csv.name)
        try:
            rows = read_csv(self.current_csv)
        except Exception as e:
            messagebox.showerror("CSV 읽기 실패", f"{e}")
            return
        if not rows:
            messagebox.showwarning("데이터 없음", "CSV에서 읽은 데이터가 없습니다.")
            return
        self._process(rows)

    def _process(self, rows: list[Row]):
        report = classify(rows, self.master)
        unmatched_now = self._collect_unmatched_unique(report.unmatched)
        if unmatched_now:
            cont = self._prompt_unmatched(unmatched_now)
            if cont:
                report = classify(rows, self.master)
        self.report = report
        self._refresh_outputs()

    def _collect_unmatched_unique(self, unmatched: list[Row]) -> list[Row]:
        seen = {}
        for r in unmatched:
            if r.asin not in seen:
                seen[r.asin] = r
        return list(seen.values())

    def _prompt_unmatched(self, unmatched: list[Row]) -> bool:
        dlg = tk.Toplevel(self.root)
        dlg.title("미매칭 ASIN 분류")
        dlg.geometry("780x500")
        dlg.transient(self.root)
        dlg.grab_set()

        header = ttk.Label(
            dlg,
            text=f"⚠ 마스터에 없는 새 ASIN {len(unmatched)}개. 카테고리를 지정하세요.",
            font=("", 11, "bold"),
            padding=10,
        )
        header.pack(fill="x")

        canvas = tk.Canvas(dlg, highlightthickness=0)
        scroll = ttk.Scrollbar(dlg, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0))
        scroll.pack(side="left", fill="y")
        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        rows_widgets = []
        for r in unmatched:
            f = ttk.Frame(inner, padding=8, relief="groove", borderwidth=1)
            f.pack(fill="x", pady=4, padx=4)
            ttk.Label(f, text=r.asin, font=("Menlo", 11, "bold")).pack(anchor="w")
            ttk.Label(f, text=(r.title or "")[:120], foreground="#555", wraplength=680).pack(anchor="w")
            row_frame = ttk.Frame(f)
            row_frame.pack(fill="x", pady=(6, 0))
            ttk.Label(row_frame, text="카테고리:").pack(side="left")
            cat_var = tk.StringVar(value=self.master["categories"][0])
            cat_combo = ttk.Combobox(
                row_frame, textvariable=cat_var, state="readonly",
                values=self.master["categories"], width=14,
            )
            cat_combo.pack(side="left", padx=(4, 12))
            ttk.Label(row_frame, text="세부(아이패치만):").pack(side="left")
            eye_var = tk.StringVar(value=EYE_SUB_NONE)
            eye_combo = ttk.Combobox(
                row_frame, textvariable=eye_var, state="disabled",
                values=[EYE_SUB_NONE] + self.master["eye_subcategories"], width=12,
            )
            eye_combo.pack(side="left", padx=(4, 0))

            def make_handler(cv=cat_var, ec=eye_combo, ev=eye_var):
                def handler(*_):
                    if cv.get() == EYE_PATCH_CAT:
                        ec.config(state="readonly")
                    else:
                        ev.set(EYE_SUB_NONE)
                        ec.config(state="disabled")
                return handler

            cat_combo.bind("<<ComboboxSelected>>", make_handler())
            rows_widgets.append((r, cat_var, eye_var))

        inner.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        btn_frame = ttk.Frame(dlg, padding=10)
        btn_frame.pack(fill="x")

        result = {"saved": False}

        def save():
            for row, cat_var, eye_var in rows_widgets:
                cat = cat_var.get()
                eye = eye_var.get() if cat == EYE_PATCH_CAT and eye_var.get() != EYE_SUB_NONE else None
                upsert_asin(self.master, row.asin, cat, eye)
            save_master(self.master)
            result["saved"] = True
            canvas.unbind_all("<MouseWheel>")
            dlg.destroy()

        def skip():
            canvas.unbind_all("<MouseWheel>")
            dlg.destroy()

        ttk.Button(btn_frame, text="건너뛰기", command=skip).pack(side="right", padx=(6, 0))
        ttk.Button(btn_frame, text="모두 저장 후 재계산", command=save).pack(side="right")

        dlg.wait_window()
        return result["saved"]

    def _refresh_outputs(self):
        for tree in (self.out1_tree, self.out2_tree):
            for item in tree.get_children():
                tree.delete(item)

        categories = self.master["categories"]
        eye_subs = self.master["eye_subcategories"]

        if self.report is None:
            for c in categories:
                self.out1_tree.insert("", "end", text=c, values=("$0.00",))
            self.out1_tree.insert("", "end", text="전체 판매수량", values=("0",))
            for s in eye_subs:
                self.out2_tree.insert("", "end", text=s, values=("$0.00", "0"))
            return

        for c in categories:
            rev, _ = self.report.by_category.get(c, (0.0, 0))
            self.out1_tree.insert("", "end", text=c, values=(f"${rev:,.2f}",))
        self.out1_tree.insert("", "end", text="전체 판매수량", values=(str(self.report.total_qty),))
        for s in eye_subs:
            rev, qty = self.report.by_eye_sub.get(s, (0.0, 0))
            self.out2_tree.insert("", "end", text=s, values=(f"${rev:,.2f}", str(qty)))

        remaining_unmatched = self._collect_unmatched_unique(self.report.unmatched)
        if remaining_unmatched:
            self.status_label.config(
                text=f"⚠ 미매칭 ASIN {len(remaining_unmatched)}개 (건너뛰어졌습니다)",
                foreground="#c00",
            )
        else:
            self.status_label.config(
                text=f"✅ 처리 완료 — {len(self.report.rows)}개 ASIN, 총 {self.report.total_qty} EA",
                foreground="#080",
            )

    def copy_output1(self):
        if self.report is None:
            return
        text = format_output1_tsv(self.report, self.master["categories"])
        self._set_clipboard(text)

    def copy_output2(self):
        if self.report is None:
            return
        text = format_output2_tsv(self.report, self.master["eye_subcategories"])
        self._set_clipboard(text)

    def _set_clipboard(self, text: str):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        self.status_label.config(text="📋 클립보드에 복사됨 — 어디든 Ctrl+V", foreground="#06c")

    def open_master_editor(self):
        MasterEditor(self.root, self.master, on_save=self._on_master_saved)

    def open_category_editor(self):
        CategoryEditor(self.root, self.master, on_save=self._on_master_saved)

    def _on_master_saved(self):
        save_master(self.master)
        if self.report is not None and self.current_csv is not None:
            try:
                rows = read_csv(self.current_csv)
                self.report = classify(rows, self.master)
            except Exception:
                pass
        self._refresh_outputs()


class MasterEditor:
    def __init__(self, parent: tk.Tk, master: dict, on_save):
        self.master = master
        self.on_save = on_save
        self.dlg = tk.Toplevel(parent)
        self.dlg.title("ASIN 마스터 편집")
        self.dlg.geometry("680x520")
        self.dlg.transient(parent)

        ttk.Label(
            self.dlg,
            text=f"저장 위치: {master_path()}",
            foreground="#666",
            padding=(10, 8),
        ).pack(fill="x")

        cols = ("category", "eye_sub")
        self.tree = ttk.Treeview(self.dlg, columns=cols, show="tree headings", height=18)
        self.tree.heading("#0", text="ASIN")
        self.tree.heading("category", text="카테고리")
        self.tree.heading("eye_sub", text="세부(아이패치)")
        self.tree.column("#0", width=140)
        self.tree.column("category", width=140)
        self.tree.column("eye_sub", width=140)
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self._refresh_tree()
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())

        btns = ttk.Frame(self.dlg, padding=(10, 0, 10, 10))
        btns.pack(fill="x")
        ttk.Button(btns, text="추가", command=self.add).pack(side="left")
        ttk.Button(btns, text="편집", command=self.edit_selected).pack(side="left", padx=4)
        ttk.Button(btns, text="삭제", command=self.delete_selected).pack(side="left")
        ttk.Button(btns, text="닫기", command=self.close).pack(side="right")

    def _refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for asin, info in sorted(self.master["asins"].items()):
            self.tree.insert(
                "", "end", iid=asin, text=asin,
                values=(info["category"], info.get("eye_sub") or ""),
            )

    def add(self):
        self._edit_dialog(None)

    def edit_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        self._edit_dialog(sel[0])

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        if messagebox.askyesno("삭제 확인", f"ASIN {sel[0]}를 삭제하시겠습니까?", parent=self.dlg):
            delete_asin(self.master, sel[0])
            self._refresh_tree()
            self.on_save()

    def _edit_dialog(self, asin: str | None):
        d = tk.Toplevel(self.dlg)
        d.title("ASIN 편집" if asin else "ASIN 추가")
        d.geometry("420x220")
        d.transient(self.dlg)
        d.grab_set()

        info = self.master["asins"].get(asin or "", {})

        ttk.Label(d, text="ASIN:").pack(anchor="w", padx=12, pady=(12, 0))
        asin_var = tk.StringVar(value=asin or "")
        asin_entry = ttk.Entry(d, textvariable=asin_var)
        asin_entry.pack(fill="x", padx=12)
        if asin:
            asin_entry.config(state="readonly")

        ttk.Label(d, text="카테고리:").pack(anchor="w", padx=12, pady=(8, 0))
        cat_var = tk.StringVar(value=info.get("category") or self.master["categories"][0])
        cat_combo = ttk.Combobox(d, textvariable=cat_var, state="readonly",
                                  values=self.master["categories"])
        cat_combo.pack(fill="x", padx=12)

        ttk.Label(d, text="세부(아이패치 카테고리일 때만):").pack(anchor="w", padx=12, pady=(8, 0))
        eye_var = tk.StringVar(value=info.get("eye_sub") or EYE_SUB_NONE)
        eye_combo = ttk.Combobox(d, textvariable=eye_var, state="readonly",
                                  values=[EYE_SUB_NONE] + self.master["eye_subcategories"])
        eye_combo.pack(fill="x", padx=12)

        def update_eye_state(*_):
            if cat_var.get() == EYE_PATCH_CAT:
                eye_combo.config(state="readonly")
            else:
                eye_var.set(EYE_SUB_NONE)
                eye_combo.config(state="disabled")
        update_eye_state()
        cat_combo.bind("<<ComboboxSelected>>", update_eye_state)

        def save():
            a = asin_var.get().strip().upper()
            if not a:
                messagebox.showerror("입력 오류", "ASIN을 입력하세요.", parent=d)
                return
            eye_val = eye_var.get() if cat_var.get() == EYE_PATCH_CAT and eye_var.get() != EYE_SUB_NONE else None
            upsert_asin(self.master, a, cat_var.get(), eye_val)
            self._refresh_tree()
            self.on_save()
            d.destroy()

        btns = ttk.Frame(d, padding=12)
        btns.pack(fill="x", side="bottom")
        ttk.Button(btns, text="저장", command=save).pack(side="right")
        ttk.Button(btns, text="취소", command=d.destroy).pack(side="right", padx=(0, 6))

    def close(self):
        self.dlg.destroy()


class CategoryEditor:
    def __init__(self, parent: tk.Tk, master: dict, on_save):
        self.master = master
        self.on_save = on_save
        self.dlg = tk.Toplevel(parent)
        self.dlg.title("카테고리 관리")
        self.dlg.geometry("520x520")
        self.dlg.transient(parent)
        self.dlg.grab_set()

        notebook = ttk.Notebook(self.dlg)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_tab(
            notebook, "전체 카테고리", "categories",
            list_kind="category",
        )
        self._build_tab(
            notebook, "아이패치 세부분류", "eye_subcategories",
            list_kind="eye_sub",
        )

        bottom = ttk.Frame(self.dlg, padding=(10, 0, 10, 10))
        bottom.pack(fill="x")
        ttk.Label(
            bottom,
            text="🛡 \"기타\", \"아이세럼패치\"는 시스템 보호 — 삭제/이름변경 불가",
            foreground="#888", font=("", 9),
        ).pack(side="left")
        ttk.Button(bottom, text="닫기", command=self.dlg.destroy).pack(side="right")

    def _build_tab(self, notebook: ttk.Notebook, label: str, key: str, list_kind: str):
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text=label)

        listbox = tk.Listbox(frame, height=12, exportselection=False)
        listbox.pack(side="left", fill="both", expand=True)
        for name in self.master[key]:
            listbox.insert("end", name)

        usage_label = ttk.Label(frame, text="", foreground="#666", padding=(8, 0))

        btn_col = ttk.Frame(frame, padding=(8, 0))
        btn_col.pack(side="left", fill="y")

        def selected_idx() -> int | None:
            sel = listbox.curselection()
            return sel[0] if sel else None

        def update_status(*_):
            idx = selected_idx()
            if idx is None:
                usage_label.config(text="")
                return
            name = self.master[key][idx]
            if list_kind == "category":
                cnt = category_in_use(self.master, name)
            else:
                cnt = eye_sub_in_use(self.master, name)
            protected = list_kind == "category" and name in PROTECTED_CATEGORIES
            tag = " (보호됨)" if protected else ""
            usage_label.config(text=f"\"{name}\" 사용 중인 ASIN: {cnt}개{tag}")

        listbox.bind("<<ListboxSelect>>", update_status)

        def refresh():
            sel = selected_idx()
            listbox.delete(0, "end")
            for name in self.master[key]:
                listbox.insert("end", name)
            if sel is not None and sel < listbox.size():
                listbox.selection_set(sel)
            update_status()
            self.on_save()

        def do_up():
            idx = selected_idx()
            if idx is None:
                return
            mover = reorder_category if list_kind == "category" else reorder_eye_sub
            new_idx = mover(self.master, idx, -1)
            if new_idx is not None:
                listbox.delete(0, "end")
                for name in self.master[key]:
                    listbox.insert("end", name)
                listbox.selection_set(new_idx)
                self.on_save()
                update_status()

        def do_down():
            idx = selected_idx()
            if idx is None:
                return
            mover = reorder_category if list_kind == "category" else reorder_eye_sub
            new_idx = mover(self.master, idx, +1)
            if new_idx is not None:
                listbox.delete(0, "end")
                for name in self.master[key]:
                    listbox.insert("end", name)
                listbox.selection_set(new_idx)
                self.on_save()
                update_status()

        def do_add():
            name = self._prompt_name("새 항목 추가", "이름:", "")
            if not name:
                return
            try:
                if list_kind == "category":
                    add_category(self.master, name)
                else:
                    add_eye_sub(self.master, name)
            except ValueError as e:
                messagebox.showerror("추가 실패", str(e), parent=self.dlg)
                return
            refresh()

        def do_rename():
            idx = selected_idx()
            if idx is None:
                return
            old = self.master[key][idx]
            if list_kind == "category" and old in PROTECTED_CATEGORIES:
                messagebox.showinfo("불가", f"\"{old}\"는 보호된 카테고리입니다.", parent=self.dlg)
                return
            new = self._prompt_name("이름 변경", f"\"{old}\"의 새 이름:", old)
            if not new or new == old:
                return
            try:
                if list_kind == "category":
                    rename_category(self.master, old, new)
                else:
                    rename_eye_sub(self.master, old, new)
            except ValueError as e:
                messagebox.showerror("이름변경 실패", str(e), parent=self.dlg)
                return
            refresh()

        def do_delete():
            idx = selected_idx()
            if idx is None:
                return
            name = self.master[key][idx]
            if list_kind == "category" and name in PROTECTED_CATEGORIES:
                messagebox.showinfo("불가", f"\"{name}\"는 보호된 카테고리입니다.", parent=self.dlg)
                return
            if list_kind == "category":
                cnt = category_in_use(self.master, name)
            else:
                cnt = eye_sub_in_use(self.master, name)
            if cnt > 0:
                messagebox.showwarning(
                    "삭제 불가",
                    f"\"{name}\"에 {cnt}개의 ASIN이 있습니다.\n\n"
                    f"먼저 'ASIN 편집'에서 이 ASIN들을 다른 카테고리로 옮긴 후 삭제하세요.",
                    parent=self.dlg,
                )
                return
            if not messagebox.askyesno("삭제 확인", f"\"{name}\"를 삭제하시겠습니까?", parent=self.dlg):
                return
            try:
                if list_kind == "category":
                    delete_category(self.master, name)
                else:
                    delete_eye_sub(self.master, name)
            except ValueError as e:
                messagebox.showerror("삭제 실패", str(e), parent=self.dlg)
                return
            refresh()

        ttk.Button(btn_col, text="▲", width=4, command=do_up).pack(pady=(0, 4))
        ttk.Button(btn_col, text="▼", width=4, command=do_down).pack(pady=(0, 12))
        ttk.Button(btn_col, text="추가", width=8, command=do_add).pack(pady=(0, 4))
        ttk.Button(btn_col, text="이름변경", width=8, command=do_rename).pack(pady=(0, 4))
        ttk.Button(btn_col, text="삭제", width=8, command=do_delete).pack()

        usage_label.pack(side="bottom", fill="x", pady=(8, 0))

    def _prompt_name(self, title: str, prompt: str, initial: str) -> str | None:
        d = tk.Toplevel(self.dlg)
        d.title(title)
        d.geometry("320x140")
        d.transient(self.dlg)
        d.grab_set()
        ttk.Label(d, text=prompt, padding=(12, 12, 12, 4)).pack(anchor="w")
        var = tk.StringVar(value=initial)
        entry = ttk.Entry(d, textvariable=var)
        entry.pack(fill="x", padx=12)
        entry.focus_set()
        entry.select_range(0, "end")
        result = {"value": None}
        def ok():
            result["value"] = var.get().strip()
            d.destroy()
        def cancel():
            d.destroy()
        btns = ttk.Frame(d, padding=12)
        btns.pack(fill="x", side="bottom")
        ttk.Button(btns, text="확인", command=ok).pack(side="right")
        ttk.Button(btns, text="취소", command=cancel).pack(side="right", padx=(0, 6))
        entry.bind("<Return>", lambda e: ok())
        entry.bind("<Escape>", lambda e: cancel())
        d.wait_window()
        return result["value"] or None


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
