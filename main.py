from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import csv

app = Flask(__name__)

CSV_FILE_PATH = 'bookings.csv'
CSV_FILE_DATA_PATH = 'data.csv'


@app.route('/')
def index():
    return 'Hello from Flask!'


def validate_bookdate(bookdate):
    bookdate_dt = datetime.fromisoformat(bookdate)
    if bookdate_dt.date() < datetime.now().date():
        return False, 'Ngày đặt bàn phải là ngày trong tương lai. Vui lòng nhập lại ngày.'
    return True, None


def validate_booktime(booktime):
    booktime_dt = datetime.fromisoformat(booktime)
    if not (12 <= booktime_dt.hour <= 22):
        return False, 'Giờ đặt bàn phải nằm trong khoảng từ 12:00 đến 22:00. Vui lòng nhập lại.'
    return True, None


def formatTime(dt):
    # Round to the nearest hour
    if dt.minute >= 30:
        dt += timedelta(hours=1)
    dt = dt.replace(minute=0, second=0, microsecond=0)

    # Return the time in HH:MM format
    return dt.strftime('%H:%M')


def is_booking_available(coso, bookdate, booktime):
    booktime_dt = datetime.fromisoformat(booktime)
    booktime_rounded = formatTime(booktime_dt)

    with open(CSV_FILE_PATH, mode='r') as file:
        reader = csv.reader(file)
        for row in reader:
            existing_coso, existing_songuoi, existing_bookdate, existing_booktime, userId = row
            # Compare with rounded time
            if (existing_coso == str(coso) and existing_bookdate == bookdate
                    and existing_booktime == booktime_rounded):
                return False

    return True


def generate_response_text(coso, songuoi, bookdate, booktime):
    bookdate_dt = datetime.fromisoformat(bookdate)
    booktime_dt = datetime.fromisoformat(booktime)
    return (
        f"Thông tin đặt bàn\n"
        f"Cơ sở: {coso}\n"
        f"Số người: {songuoi}\n"
        f"Thời gian: {bookdate_dt.strftime('%Y-%m-%d')} {booktime_dt.strftime('%H:%M')}\n"
        f"Vui lòng xác nhận hoặc hủy.")


def handle_nhaplai_thoigian(coso, songuoi, bookdate, booktime, session):
    validation_date, message_date = validate_bookdate(bookdate)
    if not validation_date:
        return generate_followup_response(coso, songuoi, session, message_date,
                                          'NhapLaiThoiGian')

    validation_time, message_time = validate_booktime(booktime)
    if not validation_time:
        return generate_followup_response(coso, songuoi, session, message_time,
                                          'NhapLaiThoiGian')

    if not is_booking_available(coso, bookdate, booktime):
        return generate_followup_response(
            coso, songuoi, session,
            'Thời gian đặt bàn này đã có người đặt. Vui lòng chọn thời gian khác.',
            'NhapLaiThoiGian2')

    response_text = generate_response_text(coso, songuoi, bookdate, booktime)
    return jsonify({
        'fulfillmentMessages': [{
            'text': {
                'text': [response_text]
            }
        }, {
            'platform': 'TELEGRAM',
            'quickReplies': {
                'title': response_text,
                'quickReplies': ['Xác nhận', 'Hủy']
            }
        }],
        'outputContexts': [{
            'name': f"{session}/contexts/confirm_booking",
            'lifespanCount': 5,
            'parameters': {
                'coso': coso,
                'songuoi': songuoi,
                'bookdate': bookdate,
                'booktime': booktime
            }
        }]
    })


def generate_followup_response_lite(eventName):
    return jsonify(
        {'followupEventInput': {
            'name': eventName,
            'languageCode': 'vi',
        }})


def generate_followup_response(coso, songuoi, session, message, eventName):
    return jsonify({
        'fulfillmentMessages': [{
            'text': {
                'text': [message]
            }
        }],
        'followupEventInput': {
            'name': eventName,
            'languageCode': 'vi',
            'parameters': {
                'coso': coso,
                'songuoi': songuoi
            }
        },
        'outputContexts': [{
            'name': f"{session}/contexts/NhapLaiThoiGian",
            'lifespanCount': 5,
            'parameters': {
                'coso': coso,
                'songuoi': songuoi
            }
        }]
    })


def getUserId(request_data):
    original_request = request_data.get('originalDetectIntentRequest',
                                        {}).get('payload',
                                                {}).get('data',
                                                        {}).get('from', {})
    return original_request.get('id', '')


def getInfo(request_data, field):
    original_request = request_data.get('originalDetectIntentRequest',
                                        {}).get('payload',
                                                {}).get('data',
                                                        {}).get('from', {})
    return original_request.get(field, '')


def checkUser(user_id):
    with open(CSV_FILE_DATA_PATH, mode='r', newline='',
              encoding='utf-8-sig') as file:
        reader = csv.reader(file)
        for row in reader:
            if row and row[0] == user_id:
                return True
    return False


def bonus(user_id):
    updated = False
    temp_file = 'temp_customer_data.csv'  # Temporary file for writing updated data

    with open(CSV_FILE_DATA_PATH, mode='r', newline='', encoding='utf-8-sig') as infile, \
         open(temp_file, mode='w', newline='', encoding='utf-8-sig') as outfile:

        reader = csv.reader(infile)
        writer = csv.writer(outfile)

        for row in reader:
            if row and row[0] == user_id:
                try:
                    new_value = int(
                        row[5]) + 1  # Incrementing the 6th column (index 5)
                    row[5] = str(new_value)  # Updating the value in the list
                    updated = True
                except ValueError:
                    continue  # Skip if the value is not an integer

            writer.writerow(row)  # Write the row to the temporary file

    if updated:
        # Replace the original file with the updated file
        import os
        os.remove(CSV_FILE_DATA_PATH)
        os.rename(temp_file, CSV_FILE_DATA_PATH)
        return True
    else:
        # If no update was made, remove the temporary file
        import os
        os.remove(temp_file)
        return False


@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    intent = req['queryResult']['intent']['displayName']
    parameters = req['queryResult']['parameters']
    session = req['session']

    print(intent)
    print(parameters)

    if intent == 'DatBan':
        coso = parameters['coso']
        songuoi = parameters['songuoi']
        bookdate = parameters['bookdate']
        booktime = parameters['booktime']

        validation_date, message_date = validate_bookdate(bookdate)
        if not validation_date:
            return generate_followup_response(coso, songuoi, session,
                                              message_date, 'NhapLaiThoiGian')

        validation_time, message_time = validate_booktime(booktime)
        if not validation_time:
            return generate_followup_response(coso, songuoi, session,
                                              message_time, 'NhapLaiThoiGian')

        if not is_booking_available(coso, bookdate, booktime):
            return generate_followup_response(
                coso, songuoi, session,
                'Thời gian đặt bàn này đã có người đặt. Vui lòng chọn thời gian khác.',
                'NhapLaiThoiGian2')

        response_text = generate_response_text(coso, songuoi, bookdate,
                                               booktime)
        return jsonify({
            'fulfillmentMessages': [{
                'text': {
                    'text': [response_text]
                }
            }, {
                'platform': 'TELEGRAM',
                'quickReplies': {
                    'title': response_text,
                    'quickReplies': ['Xác nhận', 'Hủy']
                }
            }],
            'outputContexts': [{
                'name': f"{session}/contexts/confirm_booking",
                'lifespanCount': 5,
                'parameters': {
                    'coso': coso,
                    'songuoi': songuoi,
                    'bookdate': bookdate,
                    'booktime': booktime
                }
            }]
        })

    if intent == 'DatBan - yes':
        context_params = req['queryResult']['outputContexts'][0]['parameters']
        coso = context_params['coso']
        songuoi = context_params['songuoi']
        bookdate = context_params['bookdate']
        booktime = context_params['booktime']

        booktime_dt = datetime.fromisoformat(booktime)
        booktime_rounded = formatTime(booktime_dt)

        userId = getUserId(req)

        with open(CSV_FILE_PATH, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(
                [coso, songuoi, bookdate, booktime_rounded, userId])

        if (checkUser(userId)):
            bonus(userId)
            return jsonify({
                'fulfillmentMessages': [{
                    'text': {
                        'text':
                        ['Đặt bàn của bạn đã được xác nhận. Cảm ơn bạn!']
                    }
                }, {
                    'platform': 'TELEGRAM',
                    'quickReplies': {
                        'title':
                        'Đặt bàn của bạn đã được xác nhận. Cảm ơn bạn!',
                        'quickReplies': ['Xem menu', 'Thông tin khách hàng']
                    }
                }]
            })
        else:
            return generate_followup_response_lite('NhapThongTinKhachHang')

    if intent == 'NhapLaiThoiGian' or intent == 'NhapLaiThoiGian2':
        context_params = req['queryResult']['outputContexts'][0]['parameters']
        coso = context_params['coso']
        songuoi = context_params['songuoi']
        bookdate = context_params['bookdate']
        booktime = context_params['booktime']
        return handle_nhaplai_thoigian(coso, songuoi, bookdate, booktime,
                                       session)

    if intent == 'ThongTinKhachHang':
        user_id = getUserId(req)
        response_text = ""
        found = False

        with open(CSV_FILE_DATA_PATH,
                  mode='r',
                  newline='',
                  encoding='utf-8-sig') as file:
            reader = csv.reader(file)
            for row in reader:
                if row[0] == user_id:
                    response_text += f"Thông tin khách hàng của bạn: \n"
                    response_text += f"ID: {row[0]}\n"
                    response_text += f"Tên: {row[2]}\n"
                    response_text += f"Số điện thoại: {row[3]}\n"
                    response_text += f"Email: {row[4]}\n"
                    response_text += f"Tích điểm: {row[5]}\n"
                    response_text += "--------------------\n"
                    found = True

        if found:
            return jsonify({'fulfillmentText': response_text})
        else:
            return jsonify(
                {'fulfillmentText': 'Chưa ghi nhận thông tin khách hàng'})

    if intent == 'NhapThongTinKhachHang':
        context_params = req['queryResult']['outputContexts'][0]['parameters']
        phone = context_params['phone']
        email = context_params['email']

        with open(CSV_FILE_DATA_PATH, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                getUserId(req),
                getInfo(req, 'username'),
                getInfo(req, 'first_name') + getInfo(req, 'last_name'), phone,
                email, 0
            ])

        return jsonify({
            'fulfillmentText':
            'Đặt bàn của bạn đã được xác nhận. Cảm ơn bạn!'
        })

    return jsonify(
        {'fulfillmentText': 'Cảm ơn bạn đã sử dụng dịch vụ của chúng tôi.'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
