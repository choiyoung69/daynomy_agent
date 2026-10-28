import Foundation
import Testing
@testable import DaynomyCore
struct MultipartServiceTests {
    @Test func adminNewsMultipartJSONAndBinaryImage() async throws {
        for method in ["POST","PUT"] {
            let transport=ServiceScriptTransport([(200,"{\"headerName\":\"X-CSRF\",\"token\":\"fixture\"}"),(200,"{\"id\":7}")])
            let bytes=Data([0,255,13,10,1,127])
            let result=try await service(transport).requestMultipart(path:"/api/admin/news",method:method,body:.object(["title":.string("한글\n\"제목\""),"amount":.number("1.2300")]),image:MultipartImage(data:bytes,filename:"photo.png",mimeType:"image/png"))
            #expect(result["id"]?.number == "7")
            let requests=await transport.captured();#expect(requests.count == 2)
            if requests.count == 2 {
                #expect(requests[0].url?.path == "/api/auth/csrf")
                let request=requests[1];#expect(request.httpMethod == method)
                #expect(request.value(forHTTPHeaderField:"X-CSRF") == "fixture")
                let type=try #require(request.value(forHTTPHeaderField:"Content-Type"));#expect(type.contains("multipart/form-data; boundary="))
                let data=try #require(request.httpBody);let text=String(decoding:data,as:UTF8.self)
                #expect(text.contains("name=\"request\""))
                #expect(text.contains("application/json"))
                #expect(text.contains("name=\"image\"; filename=\"photo.png\""))
                #expect(text.contains("image/png"))
                #expect(data.range(of:bytes) != nil)
                #expect(text.contains("1.2300"))
                #expect(text.contains("\\n\\\"제목\\\""))
            }
        }
    }
    @Test func multipartOptionalImageAndUnsafeFilename() async throws {
        let transport=ServiceScriptTransport([(200,"{\"headerName\":\"X-CSRF\",\"token\":\"fixture\"}"),(200,"{}")])
        _=try await service(transport).requestMultipart(path:"/api/admin/news/7",method:"PUT",body:.object(["title":.string("title")]))
        let requests=await transport.captured();let request=try #require(requests.last)
        #expect(!String(decoding:request.httpBody ?? Data(),as:UTF8.self).contains("name=\"image\""))
        for name in ["evil\r\nInjected: x.png","bad\"name.png"] {
            let bad=ServiceScriptTransport([])
            do {_=try await service(bad).requestMultipart(path:"/api/admin/news",method:"POST",body:.object([:]),image:MultipartImage(data:Data(),filename:name,mimeType:"image/png"));Issue.record("header injection accepted")} catch {#expect(await bad.captured().isEmpty)}
        }
    }
}
