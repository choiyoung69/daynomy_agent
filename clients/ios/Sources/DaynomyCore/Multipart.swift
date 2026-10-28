import Foundation

extension ServiceClient {
    public func requestMultipart(path: String, method: String = "POST", body: ServiceValue, image: MultipartImage? = nil) async throws -> ServiceValue {
        guard ["POST", "PUT"].contains(method) else { throw ServiceError(status: 0, code: "INVALID_REQUEST") }
        if let image {
            guard image.data.count <= 5 * 1024 * 1024, ["image/jpeg", "image/png", "image/webp"].contains(image.mimeType),
                  !image.filename.isEmpty, image.filename.unicodeScalars.allSatisfy({ $0.value >= 32 && $0.value != 127 }),
                  !image.filename.contains("\""), !image.filename.contains("\\") else { throw ServiceError(status: 0, code: "INVALID_IMAGE", message: "JPEG·PNG·WebP 이미지를 5MB 이하로 선택해 주세요.") }
        }
        let json = try ServiceJSON.encode(body)
        let boundary = "Daynomy-" + UUID().uuidString
        var data = Data()
        func append(_ value: String) { data.append(Data(value.utf8)) }
        append("--\(boundary)\r\nContent-Disposition: form-data; name=\"request\"\r\nContent-Type: application/json\r\n\r\n")
        append(json); append("\r\n")
        if let image {
            append("--\(boundary)\r\nContent-Disposition: form-data; name=\"image\"; filename=\"\(image.filename)\"\r\nContent-Type: \(image.mimeType)\r\n\r\n")
            data.append(image.data); append("\r\n")
        }
        append("--\(boundary)--\r\n")
        return try await requestPrepared(path: path, method: method, csrf: true, preparedBody: data, contentType: "multipart/form-data; boundary=\(boundary)")
    }
}
