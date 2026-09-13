"""Generate isolated Seed Audio sound-design assets; read credentials from stdin/env."""
import concurrent.futures
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/audio/sound-design-v2'
PROMPTS = {
    'rain-metal': '生成8秒纯环境音，无人声、无对白、无音乐。近距离雨夜，密集雨滴持续敲打老旧厚铁门，清楚的叮嗒金属质感，与下方水洼细密溅水形成两层声音。开头立即有声音，雨势中等偏大，连续稳定，有真实户外空间感，金属滴答突出。不要雷声、脚步或风暴，不要朗读任何文字。',
    'boots-corridor': '生成6秒纯动作音效，无人声、无音乐。穿厚底皮靴的高大成年人，以沉稳步伐走过安静的石质长走廊。连续六至八下清楚有力的脚步，左右脚交替，鞋跟先敲地再有鞋底闷响，步距均匀，每步有短而明显的空旷走廊回声，近距离收音。开头立即起步，最后一步自然衰减。不要其他声音，不要朗读任何文字。',
    'lock-door': '生成5秒纯拟音，无人声、无音乐。在安静室内近距离收音：开头一小串金属钥匙清脆碰撞；约1秒钥匙插入老旧门锁转动，锁舌咔哒弹开；约2秒沉重铁门缓缓打开，低沉短促的金属铰链摩擦和轻微吱呀声；最后自然衰减到安静。各动作清楚可辨，真实克制，不做恐怖尖啸。不要脚步或朗读。',
    'card-table': '生成3秒纯近距离动作音效，无人声、无音乐、无背景声。先有一张扑克牌从纸牌堆被抽出的干燥纸面摩擦声，约1秒处一张硬挺纸牌被手指轻快拍在木桌上，发出清楚、短促、轻脆的啪声，带一点纸张弹性颤动，然后自然衰减成安静。只做一次动作，不要连续洗牌，不要重击，不要朗读。',
    'suspense-bgm': '创作30秒纯器乐悬疑电影配乐，无人声、无吟唱、无对白。阴雨夜的精神病院，两个人隔桌对峙，克制而危险的心理压力。以低音大提琴长音、极低的合成器持续音和稀疏的暗色钢琴单音构成，轻微不协和弦逐渐变化，缓慢呼吸感，没有明显鼓点，不使用现有电影主题旋律。0到8秒低调建立阴冷空间，8到20秒逐渐增加弦乐层次，20到23秒压力稍稍升高但不重击，23到26秒明显抽空留下悬念，26到29秒一个孤立的低钢琴音后缓慢消散，30秒结束。为对白留出中频空间，整体深沉、细腻，有动态，不要突发惊吓音效。',
}

def main():
    key = os.environ.get('SEED_AUDIO_API_KEY') or sys.stdin.readline().strip()
    if not key:
        raise SystemExit('Missing API key')
    OUT.mkdir(parents=True, exist_ok=True)
    def generate(item):
        name, prompt = item
        pp = OUT / (name + '.prompt.txt')
        pp.write_text(prompt + '\n')
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/seed_audio_generate.py'),
            '--prompt', str(pp), '--format', 'wav', '--output', str(OUT / (name + '.wav'))],
            input=key+'\n', text=True, capture_output=True)
        print(name, result.returncode, result.stdout.replace(key, '[REDACTED]'), flush=True)
        if result.returncode:
            raise RuntimeError(name + ': ' + result.stderr.replace(key, '[REDACTED]'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(generate, PROMPTS.items()))

if __name__ == '__main__':
    main()
