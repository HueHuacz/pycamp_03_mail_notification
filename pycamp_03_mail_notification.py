""" Skrypt generujący mailowe powiadomienia na podstawie wpisów w bazie danych """

import smtplib
import sqlite3
import argparse
from email.message import EmailMessage
from email.utils import formatdate
from os import getenv
from datetime import date, timedelta
from dotenv import load_dotenv


class MailSend:
    """ Klasa obsługująca wysyłkę wiadomości mailowej """
    def __init__(self, host, port_smtp, username, password):
        """ Inicjator objektu """
        self.server = smtplib.SMTP_SSL(host, port_smtp)
        self.username = username
        self.password = password

    def __enter__(self):
        """ Logowanie do skrzynki pocztowej """
        self.server.ehlo()
        self.server.login(self.username, self.password)
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        """ Zamknięcie połączenia """
        self.server.close()

    def send_mail(self, recipient, subject, content):
        """ Wyslanie wiadomosci """
        message = self._create_message(recipient, subject, content)
        self.server.sendmail(self.username, recipient, message.as_string())

    def _create_message(self, recipient, subject, content):
        """ Tworzenie wiadomości mailowej """
        message = EmailMessage()
        message['Subject'] = subject
        message['From'] = self.username
        message['To'] = recipient
        message['Date'] = formatdate(localtime=True)
        message.set_content(content)
        return message


class Database:
    """ Klasa obsługująca połączenie z bazą danych """
    def __init__(self, database_path):
        """ Inicjator objektu """
        self.database_path = database_path
        self.conn = None
        self.cursor = None

    def __enter__(self):
        """ Utworzenia połączenia z bazą danych """
        self.conn = sqlite3.connect(self.database_path)
        self.cursor = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        """ Zamknięcie połączenia """
        self.conn.commit()
        self.conn.close()

    def add_new_book(self, book_title, book_author):
        """ Dodanie nowej książki do bazy danych """
        self.cursor.execute("""
                            INSERT INTO books(title, author)
                            VALUES (?, ?);""",
                            (book_title, book_author))

    def add_new_user(self, user_name, user_email):
        """ Dodanie nowego użytkownika do bazy danych """
        self.cursor.execute("""
                            INSERT INTO users(name, email)
                            VALUES (?, ?);""",
                            (user_name, user_email))

    def in_stock_dict(self):
        """ Słownik dostępnych, niewypożyczonych pozycji """
        self.cursor.execute("""
                            SELECT *
                            FROM books
                            WHERE borrowed = 0;""")
        result = self.cursor.fetchall()
        in_stock_dict = {i[0]: (i[1], i[2]) for i in result}
        return in_stock_dict

    def loans_dict(self):
        """ Słownik wypożyczonych pozycji """
        self.cursor.execute("""
                            SELECT users.name, books.title, loans.loan_date
                            FROM loans
                            INNER JOIN users ON loans.user_id = users.user_id
                            INNER JOIN books ON loans.book_id = books.book_id
                            WHERE return_date IS NULL;""")
        result = self.cursor.fetchall()
        loans_dict = {}
        for i in result:
            if not i[0] in loans_dict.keys():
                loans_dict[i[0]] = [(i[1], i[2])]
            else:
                loans_dict[i[0]].append((i[1], i[2]))
        return loans_dict

    def get_mail(self, user_name):
        """ Zwraca adres mail konkretnego usera """
        self.cursor.execute("""
                            SELECT email
                            FROM users
                            WHERE name = ?""",
                            (user_name,))
        result = self.cursor.fetchall()
        return result[0][0]

    def loaning(self, book, user):
        """ Wypożyczenie książki - odpowiedni status i przupisanie do usera """
        actual_date = date.today()

        if int(book) in self.in_stock_dict().keys():
            self.cursor.execute("""
                                INSERT INTO loans(book_id, user_id, loan_date)
                                VALUES (?, ?, ?);""",
                                (book, user, actual_date, ))
            self.cursor.execute("""
                                UPDATE books
                                SET borrowed = 1
                                WHERE book_id = ?;""",
                                (book,))
        else:
            return print('nie pykło')

    def returning(self, book):
        """ Zwrot książki """
        actual_date = date.today()

        if not int(book) in self.in_stock_dict().keys():
            self.cursor.execute("""
                                UPDATE loans
                                SET return_date = ?
                                WHERE book_id = ?;""",
                                (actual_date, book,))

            self.cursor.execute("""
                                UPDATE books
                                SET borrowed = 0
                                WHERE book_id = ?;""",
                                (book,))
        else:
            return print('nie pykło')


def make_parser():
    """ Parametry programu """
    parser = argparse.ArgumentParser(description='Skrypt do obsługi biblioteki', epilog='Enjoy!')
    parser.add_argument('-b', '--new_book', action='store_true', help='Dadanie nowej książki do bazy danych')
    parser.add_argument('-u', '--new_user', action='store_true', help='Dadanie nowego użytkownika do bazy danych')
    parser.add_argument('-i', '--in_stock', action='store_true', help='Lista nie wypożyczonych książek')
    parser.add_argument('-o', '--out_of_stock', action='store_true', help='Lista wypożyczonych książek')
    parser.add_argument('-s', '--send_mail', action='store_true', help='Wysłanie powiadomienia mailowego o przekroczeniu terminu wypożyczenia')
    parser.add_argument('-l', '--loaning', action='store_true', help='Nowe wypożyczenie książki przez użytkownika')
    parser.add_argument('-r', '--returning', action='store_true', help='Zwrot ksiązki przez użytkownika')
    return parser


if __name__ == '__main__':

    parser = make_parser()
    args = parser.parse_args()

    if args.new_book:
        title = input('Podaj tutuł: ')
        author = input('Podaj autora: ')

        with Database('library.db3') as db:
            db.add_new_book(title, author)

    elif args.new_user:
        name = input('Podaj imię: ')
        email = input('Podaj adres email: ')

        with Database('library.db3') as db:
            db.add_new_user(name, email)

    elif args.in_stock:
        with Database('library.db3') as db:
            print(db.in_stock_dict())

    elif args.out_of_stock:
        with Database('library.db3') as db:
            print(db.loans_dict())

    elif args.send_mail:
        actual_date = date.today()

        with Database('library.db3') as db:
            loans_dict = db.loans_dict()

        for i in loans_dict:
            for j in loans_dict[i]:

                if (termin := (actual_date - date.fromisoformat(j[1]))) > timedelta(days=10):

                    with Database('library.db3') as db:
                        i_mail = db.get_mail(i)

                    load_dotenv()

                    HOST = getenv('HOST')
                    PORT_SMTP = getenv('PORT_SMTP')
                    USERNAME = getenv('USERNAME')
                    PASSWORD = getenv('PASSWORD')

                    RECIPIENT = i_mail
                    SUBJECT = 'Przypomnienie o zwrocie ksiązki'
                    CONTENT = f'Panie! Oddej książkę: "{j[0]}".\nZostała wypożyczona: {j[1]}. Termin zwortu został przekroczony o {termin}'

                    with MailSend(HOST, PORT_SMTP, USERNAME, PASSWORD) as email:
                        email.send_mail(RECIPIENT, SUBJECT, CONTENT)

    elif args.loaning:
        book = input('Podaj numer ksiązki: ')
        user = input('Podaj numer użytkonika: ')

        with Database('library.db3') as db:
            db.loaning(book, user)

    elif args.returning:
        book = input('Podaj numer ksiązki: ')

        with Database('library.db3') as db:
            db.returning(book)
