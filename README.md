# 漫画有声书 · Comic Audiobook

把漫画PDF或图片制作成角色音色一致、富有情绪与场景声音的有声书视频。这个项目包含可复用的Codex技能，以及制作、迭代动态漫画样片时积累的脚本与提示词。

基本流程：阅读漫画与设计分镜 → 每个角色独立试音 → TA2A引用固定音色生成整段对白 → 穿插音效与BGM → 根据实际音频剪辑原画 → 字幕与试听验收 → 版本迭代和拼接。

## 仓库内容

| 路径 | 用途 |
| --- | --- |
| [skills/comic-audiobook](skills/comic-audiobook/SKILL.md) | 可安装的通用技能，包含制作规则、参考资料与通用脚本 |
| [scripts](scripts) | 当前样片的生成、混音、视频渲染和识别实验脚本 |
| [examples/prompts](examples/prompts) | 样片的角色试音、音效和最终场景提示词 |
| [examples/batman-killing-joke](examples/batman-killing-joke) | 漫画原稿、最终成片分镜图、60秒视频和字幕 |
| [AUDIO_WORKFLOW.md](AUDIO_WORKFLOW.md) | 本项目的流程约定与实际反馈记录 |

经用户选择的漫画原稿、分镜图与最终视频收录在示例目录。其他裁切图片、角色音频、中间版本、响应数据、API Key、临时依赖和模型文件保留在本地。`input/`、`output/`、`tmp/`仍在忽略规则中，仅对指定示例媒体放行。制作新漫画时重新阅读原作和选角。

## 完整示例

[![最终60秒成片的分镜图](examples/batman-killing-joke/storyboard.jpg)](examples/batman-killing-joke/final.mp4)

[查看/下载最终视频](examples/batman-killing-joke/final.mp4) · [漫画原稿](examples/batman-killing-joke/source.pdf) · [中文字幕](examples/batman-killing-joke/final.zh.srt)

采用第一段音效增强版与第二段末句怒喝版。分镜图直接从这一版最终视频抽帧，具体镜头时间见[示例说明](examples/batman-killing-joke/README.md)。

## 使用技能

将`skills/comic-audiobook`安装到你的个人Codex技能目录（通常为`~/.codex/skills/`）。已有同名技能时先比较内容，避免覆盖自己的修改。

上传漫画后，可以这样请求：

> 使用 $comic-audiobook，把这本漫画制作成有声书视频，先做一段样片。

技能涵盖独立角色参考、参考图辅助选角、连续声音叙事提示词、情绪变化、原画剪辑、字幕及实际听感验收。

## Python脚本

Python 3.10及以上版本；使用系统FFmpeg或`imageio-ffmpeg`提供的FFmpeg。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

建议新项目使用通用技能中的脚本。无需Key的请求预览：

```bash
python skills/comic-audiobook/scripts/seed_generate.py \
  --prompt input/scene.txt \
  --reference input/voices/character-a.wav \
  --reference input/voices/character-b.wav \
  --output output/audio/scene-v1.wav \
  --dry-run
```

去掉`--dry-run`会调用计费API。脚本优先读取`SEED_AUDIO_API_KEY`，也支持终端隐藏输入和`--key-stdin`；不要把真实Key写进命令、Prompt或仓库。正式TA2A请求传入实际参考音频，Prompt中的`@音频1`、`@音频2`需与数组顺序匹配。

```bash
python skills/comic-audiobook/scripts/export_subtitles.py \
  output/audio/scene-v1.json --output-prefix output/subtitles/scene-v1

python skills/comic-audiobook/scripts/render_scene.py \
  input/timeline.json --output output/video/scene-v1.mp4
```

时间线结构及混音建议见[视频制作说明](skills/comic-audiobook/references/video-and-delivery.md)。通用渲染器按真实WAV时长渲染，支持多画格、轻微推镜、中文字幕及逐字高亮。字体路径在项目时间线中配置。

根目录`scripts/`中的渲染和混音脚本保留了这次样片的布局、文件名和部分macOS字体约定，需要本地生成的`output/`中间素材才能完整重做该样片，不是新漫画的通用入口。可通过`COMIC_SOURCE_PDF`环境变量设置原漫画路径用于记录来源。最终样片可在示例目录查看。

## 重要经验

- 每个角色先建立独立、干净的参考录音；选定后固定使用。
- 将音效、音乐变化与人物对白按时间顺序交错写入Prompt。
- 默认让人物自然说完，再安排镜头；精确时间窗口只用于确有需要的节点。
- 强烈情绪通过语气、重音、呼吸和力度呈现；过多拖字、嘶吼要求可能破坏咬字。
- 生成接口的字幕与脚本一致，**不能证明实际读音正确**。情绪与咬字以试听和可用的独立识别证据检查。
- 保留旧版、请求摘要与参考散列。脚本检查和静音解码不能代替试听验收。

## 可选ASR

`scripts/local_asr_check.py`使用本地faster-whisper，不向识别器提供目标台词。需要时安装`requirements-asr.txt`，首次运行会下载模型；下载较慢时不宜阻塞样片交付。

`scripts/minimax_transcribe.py`是独立接口实验，需要支持ASR的MiniMax凭据/套餐；此前项目使用的套餐未成功调用，不能视为已经验证可用的转写方案。字幕可直接使用Seed返回的字词时间戳。

本项目的通用脚本经过离线模拟请求、字幕偏移与非30秒视频渲染验证；这些验证不产生付费API调用，也不证明实际配音效果。
