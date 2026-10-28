import SwiftUI
import DaynomyCore

@MainActor struct AccountView: View {
    let client: ServiceClient
    @Environment(AppSession.self) private var session
    @State private var nickname = ""
    @State private var feedback = ""
    @State private var message = ""
    @State private var busy = false
    @State private var confirmWithdrawal = false
    var body: some View {
        NavigationStack {
            Form {
                Section("내 계정") {
                    if let user = session.user {
                        LabeledContent("이메일", value: user.field("email").display)
                        LabeledContent("닉네임", value: user.field("nickname").display)
                        TextField("새 닉네임", text: $nickname).textContentType(.nickname).accessibilityIdentifier("nicknameField")
                        Button("닉네임 저장") { Task { await saveNickname() } }.disabled(busy || nickname.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                        Button("로그아웃") { Task { await session.logout() } }.disabled(session.busy)
                    } else {
                        Text("Google로 로그인하면 포트폴리오와 투자 기록을 저장할 수 있어요.")
                        Button("Google로 로그인") { Task { await session.login() } }.disabled(session.busy).frame(minHeight: 44)
                    }
                    if session.busy { ProgressView("계정 처리 중") }
                    if !session.error.isEmpty { Text(session.error) }
                    Button("계정 새로고침") { Task { await session.reloadProfile() } }.frame(minHeight: 44)
                }
                Section {
                    TextField("의견을 남겨 주세요", text: $feedback, axis: .vertical).lineLimit(4...10).accessibilityIdentifier("feedbackField")
                    Button("의견 보내기") { Task { await sendFeedback() } }.disabled(busy || feedback.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                } header: { Text("서비스 피드백") } footer: { Text("로그인하지 않아도 의견을 보낼 수 있어요. 개인정보나 계정 비밀번호는 적지 마세요.") }
                if busy { ProgressView("저장 중") }
                if !message.isEmpty { Section { Text(message).accessibilityIdentifier("accountMessage") } }
                if session.isAdmin { Section("관리자") { NavigationLink("서비스 관리") { AdminView(client: client) } } }
                if session.isLoggedIn {
                    Section {
                        Button("회원 탈퇴", role: .destructive) { confirmWithdrawal = true }.disabled(busy)
                    } footer: { Text("탈퇴하면 이 계정으로 저장한 기능을 이용할 수 없습니다.") }
                }
            }.navigationTitle("내 계정").scrollDismissesKeyboard(.interactively)
                .task { if let user = session.user { nickname = user.field("nickname").display } }
                .confirmationDialog("정말 탈퇴하시겠어요?", isPresented: $confirmWithdrawal, titleVisibility: .visible) {
                    Button("탈퇴", role: .destructive) { Task { await withdraw() } }
                } message: { Text("회원 탈퇴 요청은 되돌릴 수 없습니다.") }
        }
    }
    private func saveNickname() async {
        busy = true; message = ""; defer { busy = false }
        do {
            _ = try await client.request(path: "/api/users/me", method: "PATCH", body: .object(["nickname": .string(nickname)]), csrf: true)
            await session.reloadProfile(); message = "닉네임을 저장했어요."
        } catch { message = friendlyServiceError(error) }
    }
    private func sendFeedback() async {
        busy = true; message = ""; defer { busy = false }
        do {
            _ = try await client.request(path: "/api/feedback", method: "POST", body: .object(["content": .string(feedback), "pagePath": .string("/ios/account")]), csrf: true)
            feedback = ""; message = "의견을 보내 주셔서 감사합니다."
        } catch { message = friendlyServiceError(error) }
    }
    private func withdraw() async {
        busy = true; message = ""; defer { busy = false }
        do { _ = try await client.request(path: "/api/users/me", method: "DELETE", csrf: true); session.clearAfterWithdrawal(); message = "탈퇴가 처리되었어요." }
        catch { message = friendlyServiceError(error) }
    }
}
