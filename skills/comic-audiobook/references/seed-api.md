# Seed Audio 接入基线

以下形态在2026-09项目中实际使用过。换环境或报错时核对官方文档，不臆造字段或用旧凭据代替。

- [独立API Key说明](https://docs.volcengine.com/docs/6561/1816214?lang=zh)
- [音频生成HTTP接口](https://docs.volcengine.com/docs/6561/2550782?lang=zh)

`POST https://openspeech.bytedance.com/api/v3/tts/create`

Headers：`Content-Type: application/json`、独立`X-Api-Key`、本次UUID `X-Api-Request-Id`。不用App ID，旧App ID/Access Token/Secret Key组合不能替代独立Key。

```json
{"model":"seed-audio-1.0","text_prompt":"场景提示词","audio_config":{"format":"wav","sample_rate":24000,"enable_subtitle":true},"references":[{"audio_data":"实际音频Base64"}]}
```

已验证三条独立参考的使用。原接口基线最多3条、每条不超过30秒和10MB；未来变更以官方为准。超过容量时按出演角色分组，不把多人混在一条参考里冒充独立绑定。

初次选角可用`references:[{"speaker":"实际可用音色ID"}]`或`image_data`/`image_url`。图片原约束最多1张JPEG/PNG/WebP、10MB，不能与音频或speaker混用。选定后正式TA2A仍传角色录音。

响应包含Base64 `audio`及可用时的`subtitle.sentences[].words[]`；时间以毫秒计。**不是独立ASR**。字段缺失或业务失败时，不编造字幕或把空音频当成功。

## 脚本

```text
python <skill>/scripts/seed_generate.py --prompt scene.txt --reference voices/a.wav --reference voices/b.wav --output audio/scene-v1.wav --dry-run
python <skill>/scripts/seed_generate.py --prompt scene.txt --reference voices/a.wav --reference voices/b.wav --output audio/scene-v1.wav
python <skill>/scripts/seed_generate.py --prompt casting.txt --image character.png --output voices/new-v1.wav
python <skill>/scripts/export_subtitles.py audio/scene-v1.json --output-prefix subtitles/scene-v1 --offset-seconds 0
```

使用`SEED_AUDIO_API_KEY`、`--key-stdin`或终端隐藏输入。Key不进入命令行参数、技能、Prompt、模板或日志。缺少有效凭据时先完成离线分镜与文案，再说明缺失项，不能声称已生成。

`--dry-run`无网络、无需Key，只显示不含凭据/Base64的摘要。正式输出WAV、元数据JSON及`*.request.json`摘要，参考以路径和散列追溯。拒绝覆盖版本，无自动计费重试。断连或超时可能已计费，查明状态再重试。

## 独立识别

优先已有、已授权且支持任务的ASR。不要假设其他供应商Key的套餐支持ASR，也不为字幕默认引入新供应商或大型下载。不能提供完整目标台词后再把识别匹配当独立证明。识别能提供辅助证据，仍可能误听；发音和情绪以可靠的试听反馈为准。
