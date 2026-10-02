import android.content.Context;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.lang.reflect.Method;

public final class IconFetcher {
    private static Context getSystemContext() throws Exception {
        Class<?> at = Class.forName("android.app.ActivityThread");
        Method systemMain = at.getDeclaredMethod("systemMain");
        systemMain.setAccessible(true);
        Object thread = systemMain.invoke(null);
        Method getSystemContext = at.getDeclaredMethod("getSystemContext");
        getSystemContext.setAccessible(true);
        return (Context) getSystemContext.invoke(thread);
    }

    private static Bitmap render(PackageManager pm, String packageName, int size) throws Exception {
        Drawable drawable = pm.getApplicationIcon(packageName);
        Bitmap bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(bitmap);
        int iw = drawable.getIntrinsicWidth();
        int ih = drawable.getIntrinsicHeight();
        if (iw <= 0) iw = size;
        if (ih <= 0) ih = size;
        float scale = Math.min((float) size / iw, (float) size / ih);
        int w = Math.max(1, Math.round(iw * scale));
        int h = Math.max(1, Math.round(ih * scale));
        int left = (size - w) / 2;
        int top = (size - h) / 2;
        drawable.setBounds(left, top, left + w, top + h);
        drawable.draw(canvas);
        return bitmap;
    }

    private static int clampSize(String raw) {
        try { return Math.max(48, Math.min(256, Integer.parseInt(raw))); }
        catch (Exception ignored) { return 96; }
    }

    private static void batch(Context context, String[] args) throws Exception {
        int size = clampSize(args[1]);
        PackageManager pm = context.getPackageManager();
        DataOutputStream out = new DataOutputStream(System.out);
        for (int i = 2; i < args.length; i++) {
            String packageName = args[i];
            try {
                Bitmap bitmap = render(pm, packageName, size);
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                if (!bitmap.compress(Bitmap.CompressFormat.PNG, 100, bytes)) continue;
                byte[] pkg = packageName.getBytes("UTF-8");
                byte[] png = bytes.toByteArray();
                out.writeInt(pkg.length);
                out.write(pkg);
                out.writeInt(png.length);
                out.write(png);
            } catch (Throwable ignored) {
                // A single inaccessible/broken package must not abort the batch.
            }
        }
        out.writeInt(0); // stream terminator
        out.flush();
    }

    public static void main(String[] args) {
        try {
            Context context = getSystemContext();
            if (args.length >= 2 && "--batch".equals(args[0])) {
                batch(context, args);
                return;
            }
            if (args.length < 2) {
                System.err.println("Usage: IconFetcher <package> <output.png> [size] OR --batch <size> <package...>");
                System.exit(2);
            }
            String packageName = args[0];
            String outputPath = args[1];
            int size = args.length >= 3 ? clampSize(args[2]) : 192;
            Bitmap bitmap = render(context.getPackageManager(), packageName, size);
            File out = new File(outputPath);
            File parent = out.getParentFile();
            if (parent != null) parent.mkdirs();
            try (FileOutputStream fos = new FileOutputStream(out)) {
                if (!bitmap.compress(Bitmap.CompressFormat.PNG, 100, fos)) throw new RuntimeException("PNG compression failed");
                fos.flush();
            }
            System.out.println("OK " + packageName + " " + size);
        } catch (Throwable t) {
            System.err.println("ERROR " + t.getClass().getName() + ": " + t.getMessage());
            t.printStackTrace(System.err);
            System.exit(1);
        }
    }
}
