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
    @State private var showFeedback = false
    var body: some View {
        NavigationStack {
            List {
                Section("내 계정") {
                    if let user = session.user {
                        LabeledContent("이메일", value: user.field("email").display)
                        LabeledContent("닉네임", value: user.field("nickname").display)
                        TextField("새 닉네임", text: $nickname).textContentType(.nickname).accessibilityIdentifier("nicknameField")
                        Button("닉네임 저장") { Task { await saveNickname() } }.disabled(busy || nickname.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                        Button("로그아웃") { Task { await session.logout() } }.disabled(session.busy)
                    } else {
                        VStack(alignment: .leading, spacing: 20) {
                            Image(systemName: "person.crop.circle").font(.largeTitle).foregroundStyle(.tint).accessibilityHidden(true)
                            Text("내 자산을 한곳에서").font(.title2.bold())
                            Text("로그인하면 보유 자산과 거래 내역을 계정에 저장할 수 있어요.").foregroundStyle(.secondary)
                            Button { Task { await session.login() } } label: { Text("Google로 로그인").frame(maxWidth: .infinity, minHeight: 44).foregroundStyle(Color(uiColor: .systemBackground)) }
                                .buttonStyle(.borderedProminent).tint(.primary).buttonBorderShape(.capsule).disabled(session.busy)
                        }.padding(20).frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color(uiColor: .secondarySystemBackground), in: RoundedRectangle(cornerRadius: 16))
                            .listRowSeparator(.hidden)
                    }
                    if session.busy { ProgressView("계정 처리 중") }
                    if !session.error.isEmpty { Text(session.error) }
                    if !session.error.isEmpty { Button("계정 다시 확인") { Task { await session.reloadProfile() } }.frame(minHeight: 44) }
                }
                Section("서비스") {
                    Button { showFeedback = true } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 6) {
                                Text("의견 보내기").font(.headline).foregroundStyle(.primary)
                                Text("이용 중 불편했던 점을 알려주세요").font(.subheadline).foregroundStyle(.secondary)
                            }
                            Spacer(); Image(systemName: "chevron.right").foregroundStyle(.secondary)
                        }.frame(minHeight: 60)
                    }.accessibilityIdentifier("openFeedback").accessibilityLabel("의견 보내기").accessibilityHint("이용 중 불편했던 점을 알려주세요")
                }
                if busy { ProgressView("저장 중") }
                if !message.isEmpty { Section { Text(message).accessibilityIdentifier("accountMessage") } }
                if session.isAdmin { Section("관리자") { NavigationLink("서비스 관리") { AdminView(client: client) } } }
                if session.isLoggedIn {
                    Section {
                        Button("회원 탈퇴", role: .destructive) { confirmWithdrawal = true }.disabled(busy)
                    } footer: { Text("탈퇴하면 이 계정으로 저장한 기능을 이용할 수 없습니다.") }
                }
            }.listStyle(.plain).scrollContentBackground(.hidden).background(Color(uiColor: .systemBackground)).navigationTitle("내 계정").scrollDismissesKeyboard(.interactively)
                .sheet(isPresented: $showFeedback) {
                    NavigationStack {
                        Form {
                            Section {
                                TextField("의견을 남겨 주세요", text: $feedback, axis: .vertical).lineLimit(4...10).accessibilityIdentifier("feedbackField")
                                Button("의견 보내기") { Task { await sendFeedback() } }.disabled(busy || feedback.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty).accessibilityIdentifier("sendFeedback")
                            } footer: { Text("로그인하지 않아도 의견을 보낼 수 있어요. 개인정보나 계정 비밀번호는 적지 마세요.") }
                            if busy { ProgressView("저장 중") }
                            if !message.isEmpty { Text(message).accessibilityIdentifier("accountMessage") }
                        }.navigationTitle("의견 보내기").navigationBarTitleDisplayMode(.inline)
                            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("닫기") { showFeedback = false }.disabled(busy) } }
                    }
                }
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
