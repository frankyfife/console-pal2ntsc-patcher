"""PAL2NTSC, Oberflaeche / user interface.

Images hineinziehen, Patches ankreuzen, anwenden. Jede Aenderung laesst sich
ueber das Journal zuruecknehmen.
Drop images in, tick patches, apply. Every change can be reverted via the
journal.

Start:  pythonw PAL2NTSC.pyw     bzw. Doppelklick auf PAL2NTSC.bat

Autor / author: frankyfife
Lizenz / licence: MIT, siehe LICENSE / see LICENSE
https://github.com/frankyfife/console-pal2ntsc-patcher
"""
import os
import queue
import sys
import threading
import traceback

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pal2ntsc
from pal2ntsc.i18n import t, set_language, get_language, LANGUAGES
from pal2ntsc.help_text import HELP
from pal2ntsc.platforms import IMAGE_EXT

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAVE_DND = True
except Exception:
    HAVE_DND = False

BG = '#1e1f22'
FG = '#e6e6e6'
ACC = '#4a9eff'
WARN = '#e0a030'
GOOD = '#5cb85c'
DIM = '#9a9a9a'
PANEL = '#2b2d31'

SETTINGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.pal2ntsc_ui.txt')


def plat_label(p):
    return t('plat_' + p) if ('plat_' + p) in ('plat_ps1', 'plat_ps2', 'plat_gamecube',
                                               'plat_xbox', 'plat_wii') else t('plat_' + p)


class App:
    def __init__(self, root):
        self.root = root
        self.items = {}
        self.q = queue.Queue()
        self._load_lang()
        root.geometry('1080x760')
        root.minsize(920, 620)
        root.configure(bg=BG)
        self._style()
        self._build()
        self.retitle()
        self.root.after(80, self._pump)

    # --------------------------------------------------------------- setup,
    def _load_lang(self):
        try:
            with open(SETTINGS, 'r', encoding='utf-8') as f:
                code = f.read().strip()
            set_language(code)
        except Exception:
            pass

    def _save_lang(self):
        try:
            with open(SETTINGS, 'w', encoding='utf-8') as f:
                f.write(get_language())
        except Exception:
            pass

    def _style(self):
        s = ttk.Style()
        try:
            s.theme_use('clam')
        except tk.TclError:
            pass
        s.configure('.', background=BG, foreground=FG, fieldbackground=PANEL)
        s.configure('Treeview', background=PANEL, fieldbackground=PANEL,
                    foreground=FG, rowheight=24, borderwidth=0)
        s.configure('Treeview.Heading', background='#35373b', foreground=FG,
                    relief='flat')
        s.map('Treeview', background=[('selected', '#3d5a80')])
        s.configure('TButton', background='#35373b', foreground=FG, padding=6,
                    borderwidth=0)
        s.map('TButton', background=[('active', '#45474b'), ('disabled', PANEL)])
        s.configure('Accent.TButton', background=ACC, foreground='#0d1117')
        s.map('Accent.TButton', background=[('active', '#6bb0ff'),
                                            ('disabled', '#35373b')])
        s.configure('TCheckbutton', background=BG, foreground=FG)
        s.map('TCheckbutton', background=[('active', BG)])
        s.configure('TLabelframe', background=BG, foreground=DIM)
        s.configure('TLabelframe.Label', background=BG, foreground=DIM)
        s.configure('TCombobox', fieldbackground=PANEL, background=PANEL)

    def _build(self):
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill='x', padx=12, pady=(12, 6))
        self.lbl_head = tk.Label(top, text=t('ui_head'), bg=BG, fg=ACC,
                                 font=('Segoe UI', 15, 'bold'))
        self.lbl_head.pack(side='left')
        self.lbl_sub = tk.Label(top, text='   ' + t('ui_sub'), bg=BG, fg=DIM,
                                font=('Segoe UI', 9))
        self.lbl_sub.pack(side='left')

        self.lang_var = tk.StringVar(value=dict(LANGUAGES)[get_language()])
        combo = ttk.Combobox(top, textvariable=self.lang_var, width=9,
                             state='readonly',
                             values=[name for _, name in LANGUAGES])
        combo.pack(side='right', padx=(6, 0))
        combo.bind('<<ComboboxSelected>>', self.on_lang)
        self.btn_help = ttk.Button(top, text=t('ui_help'), command=self.show_help)
        self.btn_help.pack(side='right', padx=(6, 6))
        self.btn_folder = ttk.Button(top, text=t('ui_folder'), command=self.add_folder)
        self.btn_folder.pack(side='right')
        self.btn_files = ttk.Button(top, text=t('ui_files'), command=self.add_files)
        self.btn_files.pack(side='right', padx=(0, 6))
        self.btn_clear = ttk.Button(top, text=t('ui_clear'), command=self.clear)
        self.btn_clear.pack(side='right', padx=(0, 6))

        pan = tk.PanedWindow(self.root, orient='vertical', bg=BG, sashwidth=6,
                             bd=0, sashrelief='flat')
        pan.pack(fill='both', expand=True, padx=12, pady=6)

        lf = tk.Frame(pan, bg=BG)
        self.tree = ttk.Treeview(lf, columns=('platform', 'region', 'status'),
                                 show='tree headings', height=9)
        self.tree.column('#0', width=430, anchor='w')
        self.tree.column('platform', width=110, anchor='w')
        self.tree.column('region', width=120, anchor='w')
        self.tree.column('status', width=290, anchor='w')
        self.tree.tag_configure('ok', foreground=GOOD)
        self.tree.tag_configure('warn', foreground=WARN)
        self.tree.tag_configure('dim', foreground=DIM)
        sb = ttk.Scrollbar(lf, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', lambda e: self.show_details())
        pan.add(lf, minsize=170)

        df = tk.Frame(pan, bg=BG)
        self.detail_head = tk.Label(df, text=t('ui_none_selected'), bg=BG, fg=FG,
                                    font=('Segoe UI', 11, 'bold'), anchor='w',
                                    justify='left')
        self.detail_head.pack(fill='x', pady=(6, 2))
        self.detail_sub = tk.Label(df, text='', bg=BG, fg=DIM, anchor='w',
                                   justify='left', font=('Segoe UI', 9))
        self.detail_sub.pack(fill='x')
        self.notes = tk.Text(df, height=5, bg='#232529', fg=WARN, bd=0, wrap='word',
                             font=('Segoe UI', 9), highlightthickness=0, padx=8, pady=6)
        self.notes.pack(fill='x', pady=(6, 6))
        self.notes.configure(state='disabled')
        self.pf = ttk.Labelframe(df, text=t('ui_patches'))
        self.pf.pack(fill='both', expand=True)
        self.patch_area = tk.Frame(self.pf, bg=BG)
        self.patch_area.pack(fill='both', expand=True, padx=6, pady=6)
        self.patch_vars = []
        pan.add(df, minsize=230)

        act = tk.Frame(self.root, bg=BG)
        act.pack(fill='x', padx=12, pady=(0, 4))
        self.backup_var = tk.BooleanVar(value=False)
        self.cb_backup = ttk.Checkbutton(act, text=t('ui_backup'),
                                         variable=self.backup_var)
        self.cb_backup.pack(side='left')
        self.btn_patch = ttk.Button(act, text=t('ui_patch'), style='Accent.TButton',
                                    command=self.do_patch, state='disabled')
        self.btn_patch.pack(side='right')
        self.btn_undo = ttk.Button(act, text=t('ui_undo'), command=self.do_undo,
                                   state='disabled')
        self.btn_undo.pack(side='right', padx=(0, 6))
        self.btn_all = ttk.Button(act, text=t('ui_patch_all'), command=self.do_patch_all,
                                  state='disabled')
        self.btn_all.pack(side='right', padx=(0, 6))

        self.log = tk.Text(self.root, height=7, bg='#17181a', fg=DIM, bd=0,
                           wrap='word', font=('Consolas', 9), highlightthickness=0,
                           padx=8, pady=6)
        self.log.pack(fill='x', padx=12, pady=(0, 10))
        self.log.configure(state='disabled')

        if HAVE_DND:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.on_drop)
            self.say(t('ui_ready_dnd'))
        else:
            self.say(t('ui_ready_nodnd'))

    # ------------------------------------------------------------ language,
    def on_lang(self, _evt=None):
        want = self.lang_var.get()
        for code, name in LANGUAGES:
            if name == want:
                set_language(code)
                break
        self._save_lang()
        self.retitle()
        for iid in self.items:
            self._render_row(iid)
        self.show_details()

    def retitle(self):
        self.root.title(t('ui_title'))
        self.lbl_head.configure(text=t('ui_head'))
        self.lbl_sub.configure(text='   ' + t('ui_sub'))
        self.btn_help.configure(text=t('ui_help'))
        self.btn_files.configure(text=t('ui_files'))
        self.btn_folder.configure(text=t('ui_folder'))
        self.btn_clear.configure(text=t('ui_clear'))
        self.btn_patch.configure(text=t('ui_patch'))
        self.btn_undo.configure(text=t('ui_undo'))
        self.btn_all.configure(text=t('ui_patch_all'))
        self.cb_backup.configure(text=t('ui_backup'))
        self.pf.configure(text=t('ui_patches'))
        self.tree.heading('#0', text=t('ui_col_file'))
        self.tree.heading('platform', text=t('ui_col_platform'))
        self.tree.heading('region', text=t('ui_col_region'))
        self.tree.heading('status', text=t('ui_col_status'))

    def show_help(self):
        win = tk.Toplevel(self.root)
        win.title('%s - %s' % (t('ui_help'), 'PAL2NTSC'))
        win.geometry('900x680')
        win.configure(bg=BG)
        txt = tk.Text(win, bg='#17181a', fg=FG, bd=0, wrap='word',
                      font=('Consolas', 10), highlightthickness=0, padx=16, pady=12)
        sb = ttk.Scrollbar(win, orient='vertical', command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        txt.pack(side='left', fill='both', expand=True)
        txt.insert('1.0', HELP.get(get_language(), HELP['en']).strip('\n'))
        txt.configure(state='disabled')
        ttk.Button(win, text=t('ui_close'), command=win.destroy).pack(side='bottom',
                                                                     pady=8)
        win.transient(self.root)

    # --------------------------------------------------------------- helper,
    def say(self, msg):
        self.log.configure(state='normal')
        self.log.insert('end', msg + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def set_busy(self, busy):
        state = 'disabled' if busy else 'normal'
        for b in (self.btn_patch, self.btn_undo, self.btn_all):
            b.configure(state=state)
        if not busy:
            self.show_details()

    # ---------------------------------------------------------------- input,
    def on_drop(self, event):
        self.add_paths(self.root.tk.splitlist(event.data))

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title=t('ui_choose_files'),
            filetypes=[(t('ui_filter_images'), '*.iso *.bin *.img *.gcm *.cue'),
                       (t('ui_filter_all'), '*.*')])
        if paths:
            self.add_paths(paths)

    def add_folder(self):
        d = filedialog.askdirectory(title=t('ui_choose_folder'))
        if d:
            self.add_paths([d])

    def add_paths(self, paths):
        found = []
        for p in paths:
            p = p.strip('{}')
            if os.path.isdir(p):
                for root, dirs, files in os.walk(p):
                    for fn in sorted(files):
                        ext = os.path.splitext(fn)[1].lower()
                        if ext in IMAGE_EXT and ext != '.cue':
                            found.append(os.path.join(root, fn))
            elif os.path.isfile(p):
                found.append(p)
        known = {v['path'] for v in self.items.values()}
        new = [f for f in found if f not in known]
        if not new:
            self.say(t('ui_nothing_new'))
            return
        self.say(t('ui_added', n=len(new)))
        for path in new:
            iid = self.tree.insert('', 'end', text=os.path.basename(path),
                                   values=('…', '', t('ui_reading')), tags=('dim',))
            self.items[iid] = dict(path=path, info=None, error=None)
            threading.Thread(target=self._analyse, args=(iid, path),
                             daemon=True).start()

    def _analyse(self, iid, path):
        try:
            info = pal2ntsc.analyse(path)
            self.q.put(('done', iid, info, None))
        except ValueError as e:
            self.q.put(('done', iid, None, str(e)))
        except Exception:
            self.q.put(('done', iid, None, traceback.format_exc(limit=2)))

    def _pump(self):
        try:
            while True:
                kind, iid, payload, err = self.q.get_nowait()
                if kind == 'done':
                    if iid in self.items:
                        self.items[iid].update(info=payload, error=err)
                        self._render_row(iid)
                        if self.tree.selection() and self.tree.selection()[0] == iid:
                            self.show_details()
                elif kind == 'log':
                    self.say(payload)
                elif kind == 'refresh':
                    self.set_busy(False)
                    if iid in self.items:
                        self.tree.item(iid, values=('…', '', t('ui_reading')))
                        threading.Thread(target=self._analyse,
                                         args=(iid, self.items[iid]['path']),
                                         daemon=True).start()
        except queue.Empty:
            pass
        self.root.after(80, self._pump)

    def _render_row(self, iid):
        if not self.tree.exists(iid):
            return
        it = self.items[iid]
        info, err = it['info'], it['error']
        if err:
            self.tree.item(iid, values=('–', '–', err.splitlines()[-1][:80]),
                           tags=('dim',))
        elif info is None:
            self.tree.item(iid, values=('–', '–', t('ui_unrecognised')), tags=('dim',))
        else:
            j = info.extra.get('journal')
            done = j.applied_names() if j is not None else []
            open_now = [p for p in info.default_patches() if p.name not in done]
            if done and open_now:
                status, tag = t('ui_st_patched_more', n=len(open_now)), 'warn'
            elif done:
                status, tag = t('ui_st_patched'), 'ok'
            elif info.default_patches():
                status, tag = t('ui_st_available', n=len(info.default_patches())), 'warn'
            elif info.patches:
                status, tag = t('ui_st_optional'), 'dim'
            else:
                status, tag = t('ui_st_none'), 'dim'
            self.tree.item(iid, values=(t('plat_' + info.platform), info.region,
                                        status), tags=(tag,))

    def clear(self):
        for iid in list(self.items):
            if self.tree.exists(iid):
                self.tree.delete(iid)
        self.items.clear()
        self.show_details()

    # -------------------------------------------------------------- details,
    def current(self):
        sel = self.tree.selection()
        if not sel:
            return None, None
        return sel[0], self.items.get(sel[0])

    def show_details(self):
        for w in self.patch_area.winfo_children():
            w.destroy()
        self.patch_vars = []
        iid, item = self.current()
        self.notes.configure(state='normal')
        self.notes.delete('1.0', 'end')
        self.btn_all.configure(state='normal' if self.items else 'disabled')
        if not item:
            self.detail_head.configure(text=t('ui_none_selected'))
            self.detail_sub.configure(text='')
            self.notes.configure(state='disabled')
            self.btn_patch.configure(state='disabled')
            self.btn_undo.configure(state='disabled')
            return
        info, err = item['info'], item['error']
        self.detail_head.configure(text=os.path.basename(item['path']))
        if err or info is None:
            self.detail_sub.configure(text=t('ui_unusable') if err
                                      else t('ui_notrecog_long'))
            if err:
                self.notes.insert('end', err)
            self.notes.configure(state='disabled')
            self.btn_patch.configure(state='disabled')
            self.btn_undo.configure(state='disabled')
            return
        self.detail_sub.configure(
            text='%s   •   %s   •   %s %s   •   %s'
                 % (t('plat_' + info.platform), info.game_id,
                    t('ui_col_region'), info.region, info.title))
        for n in info.notes:
            self.notes.insert('end', '• ' + n + '\n')
        if not info.notes:
            self.notes.insert('end', t('ui_no_notes'))
        self.notes.configure(state='disabled')

        j = info.extra.get('journal')
        applied = j.applied_names() if j is not None else []
        if not info.patches:
            tk.Label(self.patch_area, text=t('ui_no_patches'), bg=BG, fg=DIM,
                     anchor='w').pack(fill='x')
        for p in info.patches:
            var = tk.BooleanVar(value=not p.optional and p.name not in applied)
            row = tk.Frame(self.patch_area, bg=BG)
            row.pack(fill='x', pady=1)
            ttk.Checkbutton(row, variable=var,
                            state='disabled' if p.name in applied else 'normal',
                            text=p.title + ('   (!)' if p.risky else '') +
                                 (t('ui_applied_mark') if p.name in applied else '')
                            ).pack(side='left', anchor='w')
            self.patch_vars.append((p, var))
            if p.note:
                tk.Label(self.patch_area, text='      ' + p.note, bg=BG, fg=DIM,
                         anchor='w', justify='left', font=('Segoe UI', 8),
                         wraplength=940).pack(fill='x')
        selectable = [1 for p, v in self.patch_vars if p.name not in applied]
        self.btn_patch.configure(state='normal' if selectable else 'disabled')
        self.btn_undo.configure(state='normal' if applied else 'disabled')

    # -------------------------------------------------------------- actions,
    def do_patch(self):
        iid, item = self.current()
        if not item or not item['info']:
            return
        chosen = [p.name for p, v in self.patch_vars if v.get()]
        if not chosen:
            messagebox.showinfo('PAL2NTSC', t('ui_no_checked'))
            return
        risky = [p for p, v in self.patch_vars if v.get() and p.risky]
        msg = t('ui_ask_patch', file=os.path.basename(item['path']),
                list='\n  • '.join(chosen))
        if risky:
            msg += t('ui_ask_caution', text='  '.join(p.note for p in risky))
        if not messagebox.askyesno(t('ui_patch'), msg):
            return
        self.set_busy(True)
        threading.Thread(target=self._patch_worker,
                         args=(iid, item['info'], chosen, self.backup_var.get()),
                         daemon=True).start()

    def _patch_worker(self, iid, info, chosen, backup):
        name = os.path.basename(info.extra.get('image_path', '?'))
        try:
            pal2ntsc.patch(info, selected=chosen, make_backup=backup,
                           progress=lambda m: self.q.put(('log', None, m, None)))
            self.q.put(('log', None, t('ui_done_n', file=name, n=len(chosen)), None))
        except Exception as e:
            self.q.put(('log', None, t('ui_failed', file=name, err=e), None))
        self.q.put(('refresh', iid, None, None))

    def do_patch_all(self):
        todo = [(iid, it) for iid, it in self.items.items()
                if it['info'] and it['info'].default_patches()
                and not (it['info'].extra.get('journal')
                         and it['info'].extra['journal'].applied)]
        if not todo:
            messagebox.showinfo('PAL2NTSC', t('ui_all_nothing'))
            return
        if not messagebox.askyesno(t('ui_patch_all'), t('ui_ask_all', n=len(todo))):
            return
        self.set_busy(True)
        threading.Thread(target=self._patch_all_worker,
                         args=(todo, self.backup_var.get()), daemon=True).start()

    def _patch_all_worker(self, todo, backup):
        done = fail = 0
        for iid, it in todo:
            name = os.path.basename(it['path'])
            try:
                pal2ntsc.patch(it['info'], selected=None, make_backup=backup)
                done += 1
                self.q.put(('log', None, t('ui_patched_short', file=name), None))
            except Exception as e:
                fail += 1
                self.q.put(('log', None, t('ui_failed', file=name, err=e), None))
        self.q.put(('log', None, t('ui_all_done', done=done, fail=fail), None))
        for iid, it in todo:
            self.q.put(('refresh', iid, None, None))

    def do_undo(self):
        iid, item = self.current()
        if not item:
            return
        if not messagebox.askyesno(t('ui_undo'),
                                   t('ui_ask_undo',
                                     file=os.path.basename(item['path']))):
            return
        self.set_busy(True)
        threading.Thread(target=self._undo_worker, args=(iid, item['path']),
                         daemon=True).start()

    def _undo_worker(self, iid, path):
        name = os.path.basename(path)
        try:
            rev, skipped = pal2ntsc.revert(path)
            self.q.put(('log', None, t('ui_undone', file=name, n=rev), None))
        except Exception as e:
            self.q.put(('log', None, t('ui_undo_failed', file=name, err=e), None))
        self.q.put(('refresh', iid, None, None))


def main():
    root = TkinterDnD.Tk() if HAVE_DND else tk.Tk()
    app = App(root)
    if len(sys.argv) > 1:
        app.add_paths(sys.argv[1:])
    root.mainloop()


if __name__ == '__main__':
    main()
