from google.generativeai.protos import Content, FunctionResponse, Part
from google.generativeai.types.generation_types import GenerateContentResponse
from google.protobuf.struct_pb2 import Struct
from sqlalchemy.orm import Session
from telegram import Update
from telegram.ext import MessageHandler, filters

from src.ai.ai import Functions, get_user_chat
from src.config import Config
from src.customcontext import CustomContext
from src.utils import session


async def excecute_parts(
    update: Update, context: CustomContext, response: GenerateContentResponse
):
    should_send_result = None
    function_responses = []
    bools = []
    for part in response.candidates[0].content.parts:
        fc = part.function_call
        if fc:
            return_value, should_send_result = await Functions[fc.name](
                fc.args, update, context
            )
            s = Struct()
            s.update({"result": return_value})
            function_response = Part(
                function_response=FunctionResponse(name=fc.name, response=s)
            )
            function_responses.append(function_response)
            bools.append(should_send_result)
        if part.text.strip():
            await update.message.reply_text(part.text)
    needs_further_proccessing = not all(bools)
    return Content(parts=function_responses, role="function"), needs_further_proccessing


@session
async def handler(update: Update, context: CustomContext, session: Session) -> None:
    if update.effective_user.id not in Config.BETA_GROUP:
        return

    _ = context.gettext
    ai_active = context.user_data.get("ai_active")
    if not ai_active:
        await update.message.reply_text(_("Enable AI to continue."))
        return

    chat = get_user_chat(context.user_data, session)

    text = ""
    contents = []

    if t := update.message.text:
        text = "The student said:\n" + t
        contents.append(text)

    if voice := update.message.voice:
        file = await context.bot.get_file(voice.file_id)
        bytes_ = bytes(await file.download_as_bytearray())
        text = "?"
        contents.append({"mime_type": voice.mime_type, "data": bytes_})

    response = chat.send_message(contents)

    function_response, needs_further_proccessing = await excecute_parts(
        update, context, response
    )

    if len(function_response.parts):
        if needs_further_proccessing:
            res = chat.send_message(function_response)
            await excecute_parts(update, context, res)
        else:
            chat.history.append(function_response)


aihandler = MessageHandler((filters.TEXT & (~filters.COMMAND)) | filters.VOICE, handler)
