import { useRef, useState } from 'react';
import { ActivityIndicator, Linking, Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { WebView } from 'react-native-webview';

const workspaceUrl = process.env.EXPO_PUBLIC_CLEARHIRE_URL || 'http://10.249.112.11:8765';

export default function WorkspaceScreen() {
  const webView = useRef(null);
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <SafeAreaView style={styles.fallback}>
        <StatusBar style="dark" />
        <Text style={styles.brand}>clearhire.</Text>
        <Text style={styles.title}>无法连接招聘工作台</Text>
        <Text style={styles.body}>请确认电脑和手机在同一网络，并在电脑上运行：{`\n\n`}python -m backend.server --host 0.0.0.0 --port 8765</Text>
        <Text style={styles.address}>{workspaceUrl}</Text>
        <Pressable style={styles.button} onPress={() => { setFailed(false); webView.current?.reload(); }}>
          <Text style={styles.buttonText}>重新连接</Text>
        </Pressable>
        <Pressable onPress={() => Linking.openURL(workspaceUrl)}><Text style={styles.link}>在浏览器中打开</Text></Pressable>
      </SafeAreaView>
    );
  }

  return (
    <View style={styles.container}>
      <StatusBar style="dark" />
      <WebView
        ref={webView}
        source={{ uri: workspaceUrl }}
        startInLoadingState
        renderLoading={() => <View style={styles.loading}><ActivityIndicator size="large" color="#0071e3" /><Text style={styles.loadingText}>正在连接 Clearhire…</Text></View>}
        onError={() => setFailed(true)}
        onHttpError={({ nativeEvent }) => { if (nativeEvent.statusCode >= 400) setFailed(true); }}
        onShouldStartLoadWithRequest={({ url }) => url.startsWith(workspaceUrl)}
        allowsBackForwardNavigationGestures
        pullToRefreshEnabled
        sharedCookiesEnabled={false}
        thirdPartyCookiesEnabled={false}
        setSupportMultipleWindows={false}
        style={styles.webview}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f7' },
  webview: { flex: 1, backgroundColor: '#f5f5f7' },
  loading: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center', backgroundColor: '#f5f5f7' },
  loadingText: { marginTop: 14, color: '#6e6e73', fontSize: 15 },
  fallback: { flex: 1, justifyContent: 'center', paddingHorizontal: 28, backgroundColor: '#f5f5f7' },
  brand: { color: '#0071e3', fontSize: 24, fontWeight: '700', marginBottom: 36 },
  title: { color: '#1d1d1f', fontSize: 28, fontWeight: '700', marginBottom: 14 },
  body: { color: '#515154', fontSize: 16, lineHeight: 24 },
  address: { color: '#6e6e73', fontSize: 13, marginTop: 18 },
  button: { alignItems: 'center', backgroundColor: '#0071e3', borderRadius: 12, marginTop: 28, paddingVertical: 14 },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  link: { color: '#0071e3', textAlign: 'center', fontSize: 15, marginTop: 20 },
});
