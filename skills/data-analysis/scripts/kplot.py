"""논문용 한글 그림 설정. setup_korean()으로 pyplot을 받고 save(fig, 경로)로 300dpi 저장."""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

KOREAN_FONTS = ["Malgun Gothic", "AppleGothic", "Apple SD Gothic Neo", "NanumGothic", "NanumBarunGothic",
                "Noto Sans CJK KR", "Noto Sans KR", "UnDotum"]
# 흑백 인쇄에서도 밝기로 구분되는 차분한 색
PALETTE = ["#2f4b7c", "#a05195", "#f95d6a", "#7a8ca3", "#ffa600", "#3c8d5a"]


def korean_font():
    names = {f.name for f in font_manager.fontManager.ttflist}
    for f in KOREAN_FONTS:
        if f in names:
            return f
    return None


def setup_korean(font=None):
    f = font or korean_font()
    if f:
        plt.rcParams["font.family"] = f
    else:
        print("한글 글꼴을 찾지 못했습니다. 그림의 한글이 깨질 수 있습니다(나눔고딕 등을 설치하세요).")
    plt.rcParams.update({
        "axes.unicode_minus": False, "figure.facecolor": "white", "axes.facecolor": "white",
        "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.8,
        "axes.prop_cycle": matplotlib.cycler(color=PALETTE), "font.size": 10,
        "axes.titlesize": 11, "axes.labelsize": 10, "legend.frameon": False, "savefig.bbox": "tight",
    })
    return plt


def save(fig, path, dpi=300, svg=True):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.savefig(path, dpi=dpi)
    if svg:
        fig.savefig(os.path.splitext(path)[0] + ".svg")
    plt.close(fig)
    return path
