import Foundation
@main struct CookieRace {
 static func main() async throws {
  let configuration = URLSessionConfiguration.ephemeral
  let session = URLSession(configuration:configuration)
  let base = URL(string:"http://127.0.0.1:18097")!
  let transport = URLSessionTransport(session:session)
  let client = ServiceClient(baseURL:base,transport:transport)
  let stale = Task { try await client.request(path:"/api/users/me") }
  var ready=false
  for _ in 0..<100 {
   let (data,_) = try await session.data(from:base.appendingPathComponent("probe"))
   if String(decoding:data,as:UTF8.self)=="ready" {ready=true;break}
   try await Task.sleep(for:.milliseconds(20))
  }
  guard ready else {print("FAIL refresh not pending");exit(1)}
  _ = try await client.request(path:"/api/auth/logout",method:"POST",csrf:true)
  var succeeded=false
  do {_ = try await stale.value;succeeded=true}catch{}
  try await Task.sleep(for:.seconds(1))
  let cookies = configuration.httpCookieStorage?.cookies ?? []
  let authCookies = cookies.filter { ["access_token","refresh_token"].contains($0.name) }
  print("COOKIE RACE stale succeeded \(succeeded); auth cookie count \(authCookies.count)")
  guard !succeeded,authCookies.isEmpty else {exit(1)}
  session.invalidateAndCancel()
 }
}
