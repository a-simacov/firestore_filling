from typing import Union
import decimal

import pymssql

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

from tqdm import tqdm
from tqdm.contrib.concurrent import thread_map

import tomlkit


class DataSource:

    def __init__(self, conn_props: dict = None):
        self._connection = None
        self.init_connection(conn_props)
        self.connected = self._connection is not None

    def init_connection(self, conn_props: dict):
        print('Initializing source (MS SQL) connection...')

        try:
            self._connection = pymssql.connect(**conn_props)
        except pymssql.OperationalError as e:
            error_text = '\n'.join(
                [f'{err[0]} - {err[1].decode()}' for err in e.args]
            )
            print(f'Connection error:\n{error_text}')
        except Exception as e:
            print(f'Connection error:\n{e}')

    def get(self, sql_script: str):
        cursor = self._connection.cursor(as_dict=True)

        try:
            cursor.execute(sql_script)
        except Exception as e:
            print(f'Error executing SQL:\n{sql_script}\n{e}')

        fetched_data = cursor.fetchall()
        cursor.close()

        return fetched_data


class FirestoreCollection:

    def __init__(self, firestore_client, name: str, key_id: str = None):
        self.client = firestore_client
        self.name = name
        self.key_id = key_id

    def update_docs(self, data_items: list):
        for data_item in tqdm(data_items, desc=f'Collection: {self.name:<15}'):
            self.update_doc(data_item)

    def update_docs_in_batch(self, data_items: list, request_per_batch=500):
        batch = self.client.batch()

        for index, data_item in enumerate(
                tqdm(data_items, desc=f'Collection: {self.name:<15}'),
                1
        ):
            doc_id = str(data_item.get(self.key_id))
            doc_props = self._converted_props(data_item)

            doc_ref = self.client.collection(self.name).document(doc_id)
            batch.set(doc_ref, doc_props)

            if index % request_per_batch == 0:
                self.batch_commit(batch)
                batch = self.client.batch()
        else:
            if not batch.commit_time:
                self.batch_commit(batch)

    def batch_commit(self, batch):
        try:
            batch.commit()
        except Exception as e:
            print(f'Error updating doc in {self.name}: {e}')
            exit()

    def update_docs_in_threads(self, data_items: list):
        thread_map(self.update_doc, data_items, max_workers=16,
                   desc=f'Collection {self.name:<10}')

    def update_doc(self, data_item: dict, merge=False):
        doc_id = data_item.get(self.key_id)
        doc_props = self._converted_props(data_item)

        try:
            doc_id = doc_id if doc_id is None else str(doc_id)
            self.client.collection(self.name).document(doc_id).set(
                doc_props, merge=merge)
        except Exception as e:
            print(f'Error updating doc in {self.name}: {e}\nproperties:'
                  f' {doc_props}')
            exit()

    @staticmethod
    def _converted_props(raw_doc_props: dict):
        result = {}
        for key, value in raw_doc_props.items():
            if isinstance(value, decimal.Decimal):
                result[key] = float(value)
            else:
                result[key] = value
        return result


def init_firestore_client(cloud_firestore_settings):
    print('Initializing destination (Cloud Firestore) connection...')

    try:
        cred = credentials.Certificate(
            cloud_firestore_settings['private_key_file']
        )
        firebase_admin.initialize_app(cred)

        return firestore.client()
    except Exception as e:
        print(f'Connection error:\n{e}')


def init_settings(settings_path: str) -> Union[dict, None]:
    try:
        with open(settings_path, encoding='utf-8') as reader:
            return tomlkit.parse(reader.read())
    except FileNotFoundError:
        print(f'File {settings_path} not found.')
        exit()


def export_to_firestore(settings_path):
    settings = init_settings(settings_path)

    source = DataSource(settings['ms_sql_server'])
    firestore_client = init_firestore_client(settings['cloud_firestore'])

    if not source.connected or not firestore_client:
        exit()

    cls_import_settings = settings['transfer_rules']

    print('Transferring collections...')

    for cl_import_settings in cls_import_settings['items']:
        cl_data = source.get(cl_import_settings['sql_script'])

        collection = FirestoreCollection(
            firestore_client,
            cl_import_settings['name'],
            cl_import_settings['key_id']
        )

        collection.update_docs_in_batch(cl_data)

    print('Transferring finished.')


def main():
    export_to_firestore('settings.toml')


if __name__ == '__main__':
    main()
