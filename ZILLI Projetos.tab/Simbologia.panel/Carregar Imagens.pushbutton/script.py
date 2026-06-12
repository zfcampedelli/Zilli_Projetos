# -*- coding: utf-8 -*-
"""
RecarregarImagemFamilias v11
Etapa 1: Carrega/remapeia "Type Image" no TIPO via Assembly Code
Etapa 2: Preenche "Image" na INSTANCIA via Assembly Code do tipo
"""
import os
import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")
clr.AddReference("System")
try:
    clr.AddReference("AdWindows")
except Exception:
    pass

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    FamilyInstance,
    FamilySymbol,
    BuiltInCategory,
    BuiltInParameter,
    ImageType,
    ImageTypeOptions,
    ImageTypeSource,
    Transaction,
    StorageType,
)
from pyrevit import forms, script, revit
from System.Drawing import Color, Font, Point, Size
from System import IntPtr
from System.Windows.Forms import (
    Application,
    DialogResult,
    FolderBrowserDialog,
    Form,
    FormBorderStyle,
    Label,
    NativeWindow,
    Panel,
    Screen,
)
try:
    from Autodesk.Windows import ComponentManager  # type: ignore
except Exception:
    ComponentManager = None

try:
    REVIT_UIAPP = __revit__  # type: ignore[name-defined]
except Exception:
    REVIT_UIAPP = None

# ------------------------------------------------------------------
PASTA_PADRAO     = r"X:\PadraoDesenhos\Revit\Imagens"
EXTENSOES        = [".png", ".jpg", ".jpeg", ".bmp"]
MODO_DIAGNOSTICO = False

CATEGORIAS_MEP = [
    BuiltInCategory.OST_CableTray,
    BuiltInCategory.OST_CableTrayFitting,
    BuiltInCategory.OST_Conduit,
    BuiltInCategory.OST_ConduitFitting,
    BuiltInCategory.OST_DuctCurves,
    BuiltInCategory.OST_DuctFitting,
    BuiltInCategory.OST_PipeCurves,
    BuiltInCategory.OST_PipeFitting,
    BuiltInCategory.OST_Wire,
]
# ------------------------------------------------------------------

doc    = revit.doc
output = script.get_output()
output.set_title("Recarregar Imagem - Tipos e Instancias (v11)")

# ==================================================================
# HELPERS
# ==================================================================

def construir_indice(pasta_raiz):
    indice = {}
    pastas_visitadas = set()
    # Busca recursiva em todas as subpastas (incluindo links de pasta)
    for raiz, _, arquivos in os.walk(pasta_raiz, topdown=True, followlinks=True):
        pastas_visitadas.add(raiz)
        for arq in arquivos:
            sem_ext, ext = os.path.splitext(arq)
            if ext.lower() in EXTENSOES:
                chave = sem_ext.lower()
                if chave not in indice:
                    indice[chave] = os.path.join(raiz, arq)
    return indice, sorted(pastas_visitadas)

def obter_assembly_code(elem):
    for nome in ("Assembly Code", u"C\u00f3digo de montagem"):
        try:
            p = elem.LookupParameter(nome)
            if p is not None:
                v = p.AsString()
                if v and v.strip():
                    return v.strip()
                v = p.AsValueString()
                if v and v.strip():
                    return v.strip()
        except Exception:
            pass
    return ""

def obter_param_imagem(elem):
    try:
        for p in elem.Parameters:
            try:
                if p.Definition.Name in ("Image", "Imagem", "Type Image") \
                        and p.StorageType == StorageType.ElementId:
                    return p
            except Exception:
                pass
    except Exception:
        pass
    return None

def imagem_vazia(elem):
    p = obter_param_imagem(elem)
    if p is None:
        return False
    eid = p.AsElementId()
    return eid is None or eid.IntegerValue <= 0

def safe_label(elem):
    cat = "?"
    try:
        cat = elem.Category.Name
    except Exception:
        pass
    try:
        fam = elem.Family.Name + " :: "
    except Exception:
        fam = ""
    try:
        nome = elem.Name
    except Exception:
        nome = str(elem.Id.IntegerValue)
    return "[{}] {}{}".format(cat, fam, nome)

def criar_image_type(doc, caminho):
    erros = []
    try:
        opts = ImageTypeOptions()
        opts.SetPath(caminho)
        return ImageType.Create(doc, opts)
    except Exception as e:
        erros.append("SetPath: {}".format(e))
    try:
        opts = ImageTypeOptions(caminho, False, ImageTypeSource.Import)
        return ImageType.Create(doc, opts)
    except Exception as e:
        erros.append("3args: {}".format(e))
    try:
        return ImageType.Create(doc, ImageTypeOptions(caminho))
    except Exception as e:
        erros.append("1arg: {}".format(e))
    raise Exception(" | ".join(erros))

class BarraAndamento(object):
    def __init__(self, titulo):
        self.owner = None
        self.form = Form()
        self.form.Text = titulo
        self.form.Width = 760
        self.form.Height = 28
        self.form.TopMost = False
        self.form.FormBorderStyle = getattr(FormBorderStyle, "None")
        self.form.MaximizeBox = False
        self.form.MinimizeBox = False
        self.form.ShowInTaskbar = False
        self.form.ControlBox = False

        x, y = self._posicao_acima_revit()
        self.form.Location = Point(x, y)

        self.lbl = Label()
        self.lbl.Location = Point(10, 4)
        self.lbl.Size = Size(740, 18)
        self.lbl.Font = Font("Segoe UI", 9)
        self.lbl.Text = "Iniciando..."
        self.lbl.BackColor = Color.Transparent

        self.trilha = Panel()
        self.trilha.Location = Point(0, 24)
        self.trilha.Size = Size(self.form.Width, 4)
        self.trilha.BackColor = Color.FromArgb(70, 70, 70)

        self.barra = Panel()
        self.barra.Location = Point(0, 0)
        self.barra.Size = Size(0, 4)
        self.barra.BackColor = Color.Gold
        self.trilha.Controls.Add(self.barra)

        self.form.Controls.Add(self.lbl)
        self.form.Controls.Add(self.trilha)
        self.owner = self._criar_owner_revit()
        if self.owner is not None:
            self.form.Show(self.owner)
        else:
            self.form.Show()
        Application.DoEvents()

    def _criar_owner_revit(self):
        try:
            if REVIT_UIAPP is None:
                return None
            hwnd = IntPtr(int(REVIT_UIAPP.MainWindowHandle))
            if hwnd == IntPtr.Zero:
                return None
            owner = NativeWindow()
            owner.AssignHandle(hwnd)
            return owner
        except Exception:
            return None

    def _posicao_acima_revit(self):
        area = Screen.PrimaryScreen.WorkingArea
        x_padrao = area.Left
        y_padrao = area.Top

        # Preferencia: usar bounds reais da janela do Revit.
        if ComponentManager is not None:
            try:
                app_win = ComponentManager.ApplicationWindow
                if app_win is not None:
                    left = int(app_win.Left)
                    top = int(app_win.Top)
                    width = int(app_win.Width)
                    # Fica "dentro" do topo do Revit, logo abaixo do titulo/projeto.
                    self.form.Width = max(420, width)
                    self.lbl.Size = Size(max(260, self.form.Width - 20), 18)
                    self.trilha.Size = Size(self.form.Width, 4)
                    x = left
                    y = max(area.Top, top + 32)
                    return x, y
            except Exception:
                pass

        # Fallback: monitor do handle principal do Revit.
        try:
            if REVIT_UIAPP is None:
                return x_padrao, y_padrao
            hwnd = IntPtr(int(REVIT_UIAPP.MainWindowHandle))
            if hwnd == IntPtr.Zero:
                return x_padrao, y_padrao
            bounds = Screen.FromHandle(hwnd).WorkingArea
            self.form.Width = max(420, bounds.Width)
            self.lbl.Size = Size(max(260, self.form.Width - 20), 18)
            self.trilha.Size = Size(self.form.Width, 4)
            x = bounds.Left
            y = bounds.Top
            return x, y
        except Exception:
            return x_padrao, y_padrao

    def atualizar(self, atual, total, texto):
        x, y = self._posicao_acima_revit()
        self.form.Location = Point(x, y)
        total = max(1, total)
        atual = max(0, min(atual, total))
        perc = int((100.0 * atual) / total)
        largura = int((self.trilha.Width * atual) / total)
        self.barra.Width = max(0, min(largura, self.trilha.Width))
        self.lbl.Text = "{} - {}% ({}/{})".format(texto, perc, atual, total)
        Application.DoEvents()

    def fechar(self):
        try:
            self.form.Close()
            self.form.Dispose()
            if self.owner is not None:
                self.owner.ReleaseHandle()
        except Exception:
            pass

# ==================================================================
# SELECAO DE PASTA
# ==================================================================

dlg = FolderBrowserDialog()
dlg.Description = "Selecione a pasta de imagens"
dlg.ShowNewFolderButton = False
if os.path.isdir(PASTA_PADRAO):
    dlg.SelectedPath = PASTA_PADRAO

if dlg.ShowDialog() != DialogResult.OK:
    forms.alert("Nenhuma pasta selecionada. Operacao cancelada.", exitscript=True)

PASTA_RAIZ = dlg.SelectedPath

if not os.path.isdir(PASTA_RAIZ):
    forms.alert("Pasta nao acessivel:\n{}".format(PASTA_RAIZ), exitscript=True)

# ==================================================================
# INDICE
# ==================================================================

output.print_md("Indexando imagens em `{}`...".format(PASTA_RAIZ))
indice, pastas_indexadas = construir_indice(PASTA_RAIZ)
output.print_md("Pastas indexadas: **{}**".format(len(pastas_indexadas)))
for p in pastas_indexadas[:30]:
    output.print_md("  - `{}`".format(p))
if len(pastas_indexadas) > 30:
    output.print_md("  - `...` (mais {} pastas)".format(len(pastas_indexadas) - 30))
output.print_md("   --> **{}** imagens indexadas\n".format(len(indice)))

# ==================================================================
# ETAPA 1 — TIPOS em uso no modelo sem Type Image
# ==================================================================

output.print_md("## Etapa 1 — Type Image nos Tipos\n")
output.print_md("Coletando tipos em uso no modelo...")

tipos_ids = set()
for inst in FilteredElementCollector(doc).WhereElementIsNotElementType().ToElements():
    try:
        tipos_ids.add(inst.GetTypeId())
    except Exception:
        pass

tipos_candidatos = []
for tid in tipos_ids:
    try:
        tipo = doc.GetElement(tid)
        if tipo is None:
            continue
        if obter_param_imagem(tipo) is None:
            continue
        ac = obter_assembly_code(tipo)
        if not ac:
            continue
        tipos_candidatos.append((tipo, ac))
    except Exception:
        pass

output.print_md("   --> **{}** tipos em uso com Assembly Code\n".format(len(tipos_candidatos)))

if MODO_DIAGNOSTICO:
    output.print_md("### [DIAG] Tipos candidatos:")
    for tipo, ac in tipos_candidatos[:20]:
        achou  = indice.get(ac.lower())
        vazio  = imagem_vazia(tipo)
        output.print_md(
            "  **{}** | AC=`{}` | Vazio=`{}` | Arquivo=`{}`".format(
                safe_label(tipo), ac, vazio,
                os.path.basename(achou) if achou else "NAO ENCONTRADO"
            )
        )

# ==================================================================
# ETAPA 2 — INSTANCIAS sem Image
# ==================================================================

output.print_md("## Etapa 2 — Image nas Instancias\n")
output.print_md("Coletando instancias sem Image...")

instancias_todas = []
for cat in CATEGORIAS_MEP:
    try:
        instancias_todas.extend(
            FilteredElementCollector(doc)
            .OfCategory(cat)
            .WhereElementIsNotElementType()
            .ToElements()
        )
    except Exception:
        pass
try:
    instancias_todas.extend(
        FilteredElementCollector(doc).OfClass(FamilyInstance).ToElements()
    )
except Exception:
    pass

inst_candidatas = []
for inst in instancias_todas:
    param_img = obter_param_imagem(inst)
    if param_img is None:
        continue
    if not imagem_vazia(inst):
        continue
    try:
        tipo = doc.GetElement(inst.GetTypeId())
        if tipo is None:
            continue
        ac = obter_assembly_code(tipo)
        if not ac:
            continue
        inst_candidatas.append((inst, ac, param_img))
    except Exception:
        pass

output.print_md("   --> **{}** instancias sem Image com Assembly Code\n".format(
    len(inst_candidatas)))

if MODO_DIAGNOSTICO:
    output.print_md("### [DIAG] Instancias candidatas:")
    for inst, ac, _ in inst_candidatas[:20]:
        achou = indice.get(ac.lower())
        output.print_md(
            "  **{}** | AC=`{}` | Arquivo=`{}`".format(
                safe_label(inst), ac,
                os.path.basename(achou) if achou else "NAO ENCONTRADO"
            )
        )
    output.print_md("\n> `MODO_DIAGNOSTICO = False` para executar.")
    script.exit()

if not tipos_candidatos and not inst_candidatas:
    forms.alert("Nenhum elemento para atualizar.", title="Tudo OK")
    script.exit()

# ==================================================================
# PROCESSAMENTO
# ==================================================================

output.print_md("---")

t1_ok   = []
t1_nf   = []
t1_err  = []
t2_ok   = []
t2_nf   = []
t2_err  = []
total_itens = len(tipos_candidatos) + len(inst_candidatas)
processados = 0
barra = BarraAndamento("Recarregar Imagens")
barra.atualizar(0, total_itens, "Preparando processamento")

try:
    with Transaction(doc, "pyRevit - Recarregar Imagem Tipos e Instancias") as t:
        t.Start()

        # -- Etapa 1: Tipos ----------------------------------------
        for tipo, ac in tipos_candidatos:
            caminho = indice.get(ac.lower())
            if not caminho:
                t1_nf.append((safe_label(tipo), ac))
            else:
                try:
                    img_type = criar_image_type(doc, caminho)
                    obter_param_imagem(tipo).Set(img_type.Id)
                    t1_ok.append((safe_label(tipo), ac))
                    output.print_md(
                        "  [TIPO] **{}** (`{}`) --> `{}`".format(
                            safe_label(tipo), ac, os.path.basename(caminho)
                        )
                    )
                except Exception as ex:
                    t1_err.append((safe_label(tipo), str(ex)))
                    output.print_md("  [TIPO] **{}** -- ERRO: `{}`".format(safe_label(tipo), str(ex)))

            processados += 1
            barra.atualizar(processados, total_itens, "Atualizando Tipos")

        # -- Etapa 2: Instancias -----------------------------------
        for inst, ac, param_img in inst_candidatas:
            caminho = indice.get(ac.lower())
            if not caminho:
                t2_nf.append((safe_label(inst), ac))
            else:
                try:
                    img_type = criar_image_type(doc, caminho)
                    param_img.Set(img_type.Id)
                    t2_ok.append((safe_label(inst), ac))
                    output.print_md(
                        "  [INST] **{}** (`{}`) --> `{}`".format(
                            safe_label(inst), ac, os.path.basename(caminho)
                        )
                    )
                except Exception as ex:
                    t2_err.append((safe_label(inst), str(ex)))
                    output.print_md("  [INST] **{}** -- ERRO: `{}`".format(safe_label(inst), str(ex)))

            processados += 1
            barra.atualizar(processados, total_itens, "Atualizando Instancias")

        t.Commit()
finally:
    barra.atualizar(total_itens, total_itens, "Concluido")
    barra.fechar()

# ==================================================================
# RESUMO
# ==================================================================

output.print_md(
    "---\n### Resumo\n"
    "**Tipos (Type Image)**\n"
    "- Atualizados           : **{}**\n"
    "- Arquivo nao encontrado: **{}**\n"
    "- Erros                 : **{}**\n\n"
    "**Instancias (Image)**\n"
    "- Atualizadas           : **{}**\n"
    "- Arquivo nao encontrado: **{}**\n"
    "- Erros                 : **{}**".format(
        len(t1_ok), len(t1_nf), len(t1_err),
        len(t2_ok), len(t2_nf), len(t2_err)
    )
)

if t1_nf or t2_nf:
    todos_nf = list(set([ac for _, ac in t1_nf] + [ac for _, ac in t2_nf]))
    output.print_md("\n> **Assembly Codes sem arquivo correspondente:**")
    for ac in todos_nf[:20]:
        output.print_md(">  `{}`".format(ac))
