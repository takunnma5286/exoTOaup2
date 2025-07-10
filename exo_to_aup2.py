import sys
import pprint
import glob
import os
import re
import cv2
import math
import binascii


PARAM_MAP = {
    'テキスト': {
        'サイズ': 'サイズ',
        '表示速度': '表示速度',
        'color': '文字色',
        'color2': '影・縁色',
        'font': 'フォント',
        'text': 'テキスト',
        'align': '文字揃え',
        'spacing_x': '字間',
        'spacing_y': '行間',
        'autoadjust': 'オブジェクトの長さを自動調節',
        'B': 'B',
        'I': 'I',
        'type': '文字装飾',
        '移動座標上に表示する': '移動座標上に表示',
    },
    '標準描画': {
        'X': 'X',
        'Y': 'Y',
        'Z': 'Z',
        "X軸回転": 'X軸回転',
        "Y軸回転": 'Y軸回転',
        "Z軸回転": 'Z軸回転',
        '中心X': '中心X',
        '中心Y': '中心Y',
        '中心Z': '中心Z',
        '拡大率': '拡大率',
        '透明度': '透明度',
        '回転': 'Z軸回転',
        'blend': '合成モード',
    },
    'グループ制御': {
        'X': 'X',
        'Y': 'Y',
        'Z': 'Z',
        '拡大率': '拡大率',
        'X軸回転': 'X軸回転',
        'Y軸回転': 'Y軸回転',
        'Z軸回転': 'Z軸回転',
        'range': 'range',
        'オプション': 'オプション',
    },
    '画像ファイル': {
        'file': 'ファイル',
    },
    '動画ファイル': {
        'file': 'ファイル',
        '再生速度': '再生速度',
    },
    '図形': {
        'サイズ': 'サイズ',
        '縦横比': '縦横比',
        'ライン幅': 'ライン幅',
        'type': '図形の種類',
        'color': '色',
        '角を丸くする': '角を丸くする',
    },
    '音声ファイル': {
        'file': 'ファイル',
        '再生速度': '再生速度',
        'volume': '音量',
        'pan': '左右',
        'ループ再生': 'ループ再生',
    },
    'カメラ制御': {
        'X': 'X',
        'Y': 'Y',
        'Z': 'Z',
        '目標X': '目標X',
        '目標Y': '目標Y',
        '目標Z': '目標Z',
        '目標レイヤー': '目標レイヤー',
        '傾き': '傾き',
        '視野角': '視野角',
        'range': '対象レイヤー数',
    },
    'シーン': {
        '再生位置': '再生位置',
        '再生速度': '再生速度',
        'scene': 'シーン',
        'ループ再生': 'ループ再生',
    }
}

VALUE_MAP = {
    '文字装飾': {
        '0': '標準文字', '1': '影付き文字', '2': '影付き文字(薄)',
        '3': '縁取り文字', '4': '縁取り文字(細)', '5': '縁取り文字(太)', '6': '縁取り文字(角)'
    },
    '文字揃え': {
        '0': '左寄せ[上]', '1': '中央揃え[上]', '2': '右寄せ[上]',
    },
    '合成モード': {
        '0': '通常', '1': '加算', '2': '減算', '3': '乗算', '4': 'スクリーン',
        '5': 'オーバーレイ', '6': '比較(明)', '7': '比較(暗)', '8': '輝度',
        '9': '色差', '10': '陰影', '11': '明暗', '12': '差分'
    },
    '図形の種類': {
        '0': '背景', '1': '円', '2': '四角形', '3': '三角形', '4': '五角形', '5': '六角形', '6': '星型'
    }
}

EFFECT_NAMES = [
    'テキスト',
    '標準描画',
    'グループ制御',
    'アニメーション効果',
    '画像ファイル',
    '動画ファイル',
    '図形'
]

EFFECT_RENAME_MAP = {
    'シャドー': 'ドロップシャドウ'
}

def json_to_exo(json_data, heddername):
    exo_lines = []
    exo_lines.append(f"[{heddername}]")
    
    for key, value in json_data.items():
        if isinstance(value, dict):
            exo_lines.append(f"[{key}]")
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, list):
                    sub_value = ",".join(str(v) for v in sub_value)
                exo_lines.append(f"{sub_key}={sub_value}")
        else:
            if isinstance(value, list):
                value = ",".join(str(v) for v in value)
            exo_lines.append(f"{key}={value}")
    
    return "\n".join(exo_lines)

def overwrite_value(obj_dict, conv_map, no_remove=False):
    new_dict = {}
    for k, v in obj_dict.items():
        if k in conv_map:
            parsed = parse_easing_nums(v)
            if parsed != v:
                new_dict[conv_map[k]] = parsed
            else:
                new_dict[conv_map[k]] = v
        elif no_remove:
            new_dict[k] = v
    return new_dict

def parse_exo(file_path):
    exo_data = {}
    current_section = None
    try:
        with open(file_path, 'r', encoding='shift_jis') as f:
            for line in f:
                line = line.strip()
                if line.startswith('[') and line.endswith(']'):
                    section_name = line[1:-1]
                    current_section = exo_data.setdefault(section_name, {})
                elif '=' in line and current_section is not None:
                    key, value = line.split('=', 1)
                    current_section[key] = value
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    return exo_data

def parse_easing_nums(easing_str):
    # exo: "0.0,100.0,15@イージング（通常）@イージング,14"
    # aup2: "0.00,100.00,イージング（通常）@イージング,0|14"
    parts = easing_str.split(',')
    if len(parts) < 3:
        return easing_str  # fallback

    # First two: float with 2 decimals
    v1 = f"{float(parts[0]):.2f}"
    v2 = f"{float(parts[1]):.2f}"

    # "15@イージング（通常）@イージング"
    third = parts[2]
    if '@' in third:
        num, *rest = third.split('@')
        easing_name = '@'.join(rest)
        easing_num = int(num)
    else:
        easing_name = third
        easing_num = 0

    # "14"
    fourth = parts[3] if len(parts) > 3 else "0"

    if easing_name == "Type1@Curve Editor":
        bezier = decode_CurveEditor_bezier(int(fourth))
        if bezier:
            return f"{v1},{v2},直線移動(時間制御),0|{bezier[0]:.2f},{bezier[1]:.2f},{(1 - bezier[2]):.2f},{(1 - bezier[3]):.2f}"
    # v1,v2,easing_name,0|fourth
    return f"{v1},{v2},{easing_name},0|{fourth}"

def parse_effect_conf(file_path):
    anim_map = {}
    in_anim_section = False
    in_old_script_section = False
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line == '[OldScript.アニメーション効果]':
                    in_anim_section = True
                elif line.startswith('['):
                    in_old_script_section = True
                    if line.startswith('[OldScript.') and line.endswith(']'):
                        section_name = line[1:-1]
                        anim_map[section_name] = {}
                elif (in_anim_section or in_old_script_section) and '=' in line:
                    key, value = line.split('=', 1)
                    if in_anim_section:
                        anim_map[key] = value
                    elif in_old_script_section:
                        anim_map[section_name][key] = value
    except Exception as e:
        print(f"Error parsing effect.conf: {e}", file=sys.stderr)
    return anim_map

def parse_animation_script(file_path):
    """Parses an animation script file (.anm, .anm2) to get parameter mappings."""
    anim_map = {}
    current_effect = None
    param_re = re.compile(r"--(track|check)(?:@(\w+)|(\d+)):([^,]+)")

    # Use shift_jis for .anm files, utf-8 for others (e.g., .anm2)
    encoding = 'shift_jis' if file_path.endswith('.anm') else 'utf-8'

    try:
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line.startswith('@'):
                    if file_path.split("\\")[-1][0] == "@":
                        current_effect = line[1:].split('@', 1)[0] + file_path.split("\\")[-1].split(".")[0]
                    else:
                        current_effect = line[1:].split('@', 1)[0]
                    anim_map[current_effect] = {}
                elif current_effect and line.startswith('--'):
                    match = param_re.match(line)
                    if match:
                        param_type = match.group(1)
                        var_name = match.group(2)
                        num_name = match.group(3)
                        param_label = match.group(4).strip()
                        key = var_name if var_name else f"{param_type}{num_name}"
                        anim_map[current_effect][key] = param_label
    except Exception as e:
        print(f"Error parsing animation script {file_path} with encoding {encoding}: {e}", file=sys.stderr)
    return anim_map

def parse_all_animation_scripts(directory):
    """Parses all .anm and .anm2 files in a directory and merges the results."""
    all_param_maps = {}
    script_files = glob.glob(os.path.join(directory, '*.anm*'))

    for script_file in script_files:
        parsed_map = parse_animation_script(script_file)
        for effect, params in parsed_map.items():
            if effect not in all_param_maps:
                all_param_maps[effect] = {}
            all_param_maps[effect].update(params)
            
    return all_param_maps

def decode_CurveEditor_bezier(code):
    INT32_MAX = 2147483647
    tmp = 0

    if -12368443 >= code >= -INT32_MAX:
        tmp = code + INT32_MAX
    elif 12368443 <= code < INT32_MAX:
        tmp = code + 2122746762
    else:
        # ベジェ曲線用のコード範囲外
        return None

    # iy2 = floor(tmp / 6600047)
    iy2 = tmp // 6600047
    # ix2 = floor((tmp - iy2 * 6600047) / 65347)
    ix2 = (tmp - iy2 * 6600047) // 65347
    # iy1 = floor((tmp - (iy2 * 6600047 + ix2 * 65347)) / 101)
    iy1 = (tmp - (iy2 * 6600047 + ix2 * 65347)) // 101
    # ix1 = (tmp - (iy2 * 6600047 + ix2 * 65347)) % 101
    ix1 = (tmp - (iy2 * 6600047 + ix2 * 65347)) % 101

    iy1 -= 273
    iy2 -= 273

    x1 = ix1 * 0.01
    y1 = iy1 * 0.01
    x2 = ix2 * 0.01
    y2 = iy2 * 0.01

    return (x1, y1, x2, y2)

def decode_exo_text(hex_str):
    try:
        byte_data = binascii.unhexlify(hex_str)
        return byte_data.decode('utf-16-le').rstrip('\x00')
    except (binascii.Error, UnicodeDecodeError):
        return hex_str
    

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python exo_to_aup2-2.py <Root.exo> <Scene1.exo> <output.aup2>")
        sys.exit(1)

    input_exo_paths = sys.argv[1:-1]
    output_aup2_path = sys.argv[-1]

    print("Parsing effect / animation scripts...")
    effect_map = parse_effect_conf('AviUtl2_doc/effect.conf')
    anim_map = parse_all_animation_scripts("./Script")

    # Cache Video fps
    # Path:fps
    video_fps = {
    }
    padding = 0
    output_str = ""

    Default_Scene = 1

    scene_hedders = []
    parsed_datas = []
    # for ONLY 再生位置 in scene obj
    print("Parsing scene header...")
    for i in range(len(input_exo_paths)):
        parsed_data = parse_exo(input_exo_paths[i])
        if parsed_data and "exedit" in parsed_data:
            parsed_datas.append(parsed_data)
            scene_hedders.append(parsed_data["exedit"])

    for exo_num in range(len(input_exo_paths)):
        input_exo_path = input_exo_paths[exo_num]
        exo_name = os.path.basename(input_exo_path)
        print(f"Parsing EXO file ({input_exo_path}) to dict...")
        parsed_data = parsed_datas[exo_num]

        if parsed_data:
            print(f"Successfully parsed")
            #pprint.pprint(parsed_data)

            print("Converting to AUP2 format...")
            print("reading hedder...")
            #make aup2 header
            prj_hedder = {
                "file": output_aup2_path,
                "display.scene": 0,
            }
            output_str += json_to_exo(prj_hedder, "project") + "\n"


            #read hedder
            hedder = {
                "scene": 0,
                "name": "Root",
                "video.width": 1280,
                "video.height": 720,
                "video.rate": 60,
                "video.scale": 1,
                "audio.rate": 44100,
                "cursor.frame": 0,
                "display.frame": 0,
                "display.layer": 1,
                "display.zoom": 1000000,
                "display.order": 0,
                "display.camera": "",
            }
            old_hedder = parsed_data["exedit"]
            hedder["scene"] = exo_num
            hedder["name"] = exo_name.rsplit(".")[0]
            hedder["video.width"] = int(old_hedder["width"])
            hedder["video.height"] = int(old_hedder["height"])
            hedder["video.rate"] = int(old_hedder["rate"])
            hedder["audio.rate"] = int(old_hedder["audio_rate"])
            output_str += json_to_exo(hedder, f"scene.{exo_num}") + "\n"

            print("reading items...")
            i = 0
            while str(i) in parsed_data:
                item_config = {
                    "layer": 0,
                    "frame": [0, 0],
                    "scene":0
                }
                old_item_config = parsed_data[str(i)]
                item_config["layer"] = int(old_item_config["layer"]) - 1
                item_config["frame"] = [int(old_item_config["start"]) - 1, int(old_item_config["end"]) - 1]
                item_config["scene"] = exo_num
                output_str += json_to_exo(item_config, f"{i + padding}") + "\n"

                m = 0
                item_type = {}
                old_item_type = parsed_data[f"{i}.{m}"]
                effect_name = old_item_type["_name"]
                if effect_name in ["カスタムオブジェクト", "フレームバッファ"]:
                    effect_name = "標準描画"
                if effect_name in PARAM_MAP:
                    item_type = overwrite_value(old_item_type, PARAM_MAP[effect_name])
                else:
                    print(f"Warning: Effect '{effect_name}' not found in PARAM_MAP. Using default values.")

                if old_item_type["_name"] == "図形":
                    item_type["角を丸くする"] = "0"
                    item_type["図形の種類"] = VALUE_MAP["図形の種類"][old_item_type["type"]] if old_item_type.get("type") else VALUE_MAP["図形の種類"]["0"]
                
                elif old_item_type["_name"] == "テキスト":
                    item_type["テキスト"] = decode_exo_text(old_item_type.get("text", ""))
                elif old_item_type["_name"] in ["音声ファイル", "動画ファイル"]:
                    if "再生位置" in item_type.keys():
                        item_type.pop("再生位置")

                    file_path = old_item_type.get("file")
                    if file_path and file_path not in video_fps:
                        abs_file_path = os.path.abspath(file_path)
                        fps_value = 30
                        try:
                            cap = cv2.VideoCapture(abs_file_path)
                            if cap.isOpened():
                                fps_value = cap.get(cv2.CAP_PROP_FPS)
                                if not fps_value or fps_value <= 1:
                                    fps_value = 30
                            cap.release()
                        except Exception:
                            fps_value = 30
                            print(f"Warning: Could not read FPS from video file '{abs_file_path}'. Using default value 30.")
                        video_fps[file_path] = fps_value

                    fps = video_fps.get(file_path, 30)
                    start = float(old_item_config.get("start", 0)) / fps
                    end = float(old_item_config.get("end", 0)) / fps
                    speed = float(old_item_type.get("再生速度", 1)) / 100
                    long = (end - start) * speed
                    video_start = float(old_item_type["再生位置"]) / fps
                    item_type["再生位置"] = f"{video_start},{video_start + long},再生範囲,0"

                elif old_item_type["_name"] == "シーン":
                    if "scene" in old_item_type.keys():
                        Default_Scene = int(old_item_type["scene"])
                    else:
                        item_type["シーン"] = Default_Scene
                    
                    if "再生位置" in old_item_type.keys():
                        item_type["再生位置"] = (float(old_item_type["再生位置"]) - 1) / float(scene_hedders[int(item_type["シーン"])]["rate"])

                elif old_item_type["_name"] in ["グループ制御", "カメラ制御"]:
                    item_type["対象レイヤー数"] = old_item_type["range"]
                    item_type.pop("range")
                

                item_type["effect.name"] = effect_name
                output_str += json_to_exo(item_type, f"{i + padding}.{m}") + "\n"
                skiped = 0
                while f"{i}.{m + 1}" in parsed_data:
                    m += 1
                    old_item_item = parsed_data[f"{i}.{m}"]

                    if "blend" in old_item_item.keys(): # 標準描画とか、または、さいごのもの、の条件のほうが適切
                        old_item_item["blend"] = VALUE_MAP["合成モード"].get(old_item_item["blend"], "通常") # get関数でない場合は通常これにするよを指定できるの知らなかった...

                    if old_item_item["_name"] in ["アニメーション効果", "カスタムオブジェクト"]:
                        anim_name = old_item_item.get("name") if old_item_item.get("name") else "震える"
                        if anim_name in anim_map:
                            item_item = overwrite_value(old_item_item, anim_map[anim_name])
                            item_item["effect.name"] = anim_name
                            output_str += json_to_exo(item_item, f"{i + padding}.{m - skiped}") + "\n"
                        else:
                            print(f"Warning: Animation effect '{anim_name}' not found in animation scripts. Skip this item.")
                            skiped += 1  # Skip this item
                            #item_item = old_item_item           
                    
                    elif old_item_item["_name"] in ["標準描画", "拡張描画"]:
                        item_view = {
                            "effect.name" : "標準描画",
                            "X": 0.00,
                            "Y": 0.00,
                            "Z": 0.00,
                            "中心X": 0.00,
                            "中心Y": 0.00,
                            "中心Z": 0.00,
                            "X軸回転": 0.00,
                            "Y軸回転": 0.00,
                            "Z軸回転": 0.00,
                            "拡大率": 100.000,
                            "縦横比": 0.000,
                            "透明度": 0.00,
                            "合成モード": "通常",
                        }
                        if old_item_type["_name"] == "動画ファイル":
                            old_item_item["音量"] = 0.00
                            item_view["音量"] = 0.00
                            item_view["effect.name"] = "映像再生"
                        item_view = {**item_view, **overwrite_value(old_item_item, PARAM_MAP["標準描画"])}
                        output_str += json_to_exo(item_view, f"{i + padding}.{m - skiped}") + "\n"
                        
                    elif old_item_item["_name"] in ["標準再生"]:
                        item_view = {
                            "音量": 100.00,
                            "左右": 0.00,
                        }
                        item_view = {**item_view, **overwrite_value(old_item_item, PARAM_MAP["音声ファイル"])}
                        item_view["effect.name"] = "音声再生"
                        output_str += json_to_exo(item_view, f"{i + padding}.{m - skiped}") + "\n"
                    
                    elif old_item_item["_name"] == "スクリプト制御":
                        item_item = {}
                        item_item["effect.name"] = "スクリプト制御"
                        item_item["テキスト"] = decode_exo_text(old_item_item.get("text", ""))
                        output_str += json_to_exo(item_item, f"{i + padding}.{m - skiped}") + "\n"
                        
                    else: # effects
                        if old_item_item["_name"] in EFFECT_RENAME_MAP:
                            old_item_item["_name"] = EFFECT_RENAME_MAP[old_item_item["_name"]]
                        if old_item_item["_name"] == "マスク":
                            old_item_item["マスクの種類"] = VALUE_MAP["図形の種類"].get(old_item_item.get("type"), VALUE_MAP["図形の種類"]["0"])
                        if f"OldScript.{old_item_item["_name"]}" in effect_map:
                            item_other = overwrite_value(old_item_item, effect_map[f"OldScript.{old_item_item["_name"]}"], no_remove=True)
                        else:
                            item_other = dict(old_item_item)
                            print(f"Warning: Effect '{old_item_item['_name']}' not found in effect.conf. Using default values.")
                        item_other["effect.name"] = item_other.pop("_name")
                        output_str += json_to_exo(item_other, f"{i + padding}.{m - skiped}") + "\n"
                i += 1 
            padding = i + padding  # Update padding for next items
            print(f"Successfully parsed {i} items.")
        else:
            print(f"Error: Failed to parse EXO file {input_exo_path}. Skipping this file.")
            continue


    # 保存
    abs_output_path = os.path.abspath(output_aup2_path)
    output_str = output_str.replace("〜", "～")
    print(f"Writing output to {abs_output_path}...")
    with open(abs_output_path, 'w', encoding='utf-8') as f:
        f.write(output_str)
    print("Conversion completed successfully.")