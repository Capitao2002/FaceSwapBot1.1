from flask import Flask, request
import telegram
import os
import logging
import threading
from swap_face import process_video
from bot_config import TELEGRAM_TOKEN

app = Flask(__name__)
bot = telegram.Bot(token=TELEGRAM_TOKEN)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_sessions = {}

def cleanup_files(*file_paths):
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"🧹 Arquivo removido: {path}")
        except Exception as e:
            logger.warning(f"⚠️ Falha ao remover arquivo {path}: {e}")

def process_and_send(chat_id, video_path, photo_path, output_path):
    bot.send_message(chat_id, "🛠️ Processando vídeo... Isso pode levar alguns segundos.")
    try:
        process_video(video_path, photo_path, output_path)
        if os.path.exists(output_path):
            with open(output_path, 'rb') as out_vid:
                bot.send_video(chat_id, out_vid, caption="✅ Aqui está seu vídeo com o rosto trocado.")
            logger.info(f"🎉 Vídeo processado enviado para {chat_id}")
        else:
            bot.send_message(chat_id, "❌ Ocorreu um erro: o vídeo final não foi gerado.")
            logger.error(f"❌ Vídeo de saída não encontrado: {output_path}")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Falha ao processar o vídeo: {e}")
        logger.exception("Erro ao processar vídeo")
    finally:
        cleanup_files(video_path, photo_path, output_path)
        if chat_id in user_sessions:
            del user_sessions[chat_id]

@app.route('/', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    chat_id = update.message.chat.id

    try:
        if update.message.video:
            video = update.message.video.get_file()
            file_size = update.message.video.file_size
            max_video_size = 50 * 1024 * 1024  # 50 MB limite

            if file_size > max_video_size:
                bot.send_message(chat_id, "⚠️ O vídeo é muito grande. Por favor, envie um vídeo com até 50MB.")
                return 'ok'

            file_path = f'static/input_{chat_id}.mp4'
            video.download(file_path)
            user_sessions[chat_id] = {'video': file_path}
            bot.send_message(chat_id, "🎥 Vídeo recebido com sucesso. Agora envie uma imagem com o rosto desejado.")
            logger.info(f"✅ Vídeo recebido de {chat_id} e salvo em {file_path}")

        elif update.message.photo:
            if chat_id not in user_sessions or 'video' not in user_sessions[chat_id]:
                bot.send_message(chat_id, "⚠️ Por favor, envie primeiro o vídeo antes da imagem.")
                logger.warning(f"Imagem recebida antes do vídeo por {chat_id}")
                return 'ok'

            photo = update.message.photo[-1].get_file()
            photo_path = f'static/face_{chat_id}.jpg'
            photo.download(photo_path)
            logger.info(f"✅ Imagem de rosto recebida de {chat_id} e salva em {photo_path}")

            video_path = user_sessions[chat_id]['video']
            output_path = f'static/output_{chat_id}.mp4'

            thread = threading.Thread(target=process_and_send, args=(chat_id, video_path, photo_path, output_path))
            thread.start()

        else:
            bot.send_message(chat_id, "📤 Por favor, envie um vídeo (.mp4) e depois uma imagem com o rosto a ser usado.")

    except Exception as e:
        logger.exception("❌ Erro no webhook")
        bot.send_message(chat_id, "❌ Ocorreu um erro inesperado. Tente novamente mais tarde.")

    return 'ok'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
