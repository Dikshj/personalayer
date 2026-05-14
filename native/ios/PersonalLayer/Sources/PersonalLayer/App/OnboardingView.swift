import SwiftUI

struct OnboardingView: View {
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false
    @State private var step = 0

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            if step == 0 {
                Image(systemName: "brain.head.profile")
                    .font(.system(size: 80))
                    .foregroundColor(.blue)
                Text("Welcome to Personal Layer")
                    .font(.largeTitle.bold())
                Text("Your private context layer. All data stays on your device.")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
            } else if step == 1 {
                Image(systemName: "lock.shield")
                    .font(.system(size: 80))
                    .foregroundColor(.green)
                Text("Privacy First")
                    .font(.largeTitle.bold())
                Text("No cloud storage of raw events. No behavioral tracking. You control everything.")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
            } else if step == 2 {
                Image(systemName: "arrow.triangle.2.circlepath")
                    .font(.system(size: 80))
                    .foregroundColor(.orange)
                Text("Connect Your Services")
                    .font(.largeTitle.bold())
                Text("Link Gmail, Calendar, Spotify, and more. We only read metadata — never content.")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
            }

            Spacer()

            HStack(spacing: 16) {
                if step > 0 {
                    Button("Back") { step -= 1 }
                        .buttonStyle(.bordered)
                }
                Button(step == 2 ? "Get Started" : "Next") {
                    if step == 2 {
                        hasCompletedOnboarding = true
                    } else {
                        step += 1
                    }
                }
                .buttonStyle(.borderedProminent)
            }
            .padding(.bottom, 32)
        }
        .padding()
    }
}
