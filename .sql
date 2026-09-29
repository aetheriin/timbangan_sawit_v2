USE DbSistemTimbangan;
GO

SELECT nama_driver, DATALENGTH(face_embedding_data) AS ukuran_byte FROM driver;