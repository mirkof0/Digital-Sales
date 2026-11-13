from digital_sales.get_data import build_database, download_raw


def main() -> None:
    csv_path = download_raw()
    build_database(csv_path)


if __name__ == "__main__":
    main()