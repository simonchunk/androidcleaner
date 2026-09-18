import android.content.Context;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;
import java.io.File;
import java.io.FileOutputStream;
import java.lang.reflect.Method;

public final class IconFetcher {
    private static Context getSystemContext() throws Exception {
        Class<?> at = Class.forName("android.app.ActivityThread");

        // app_process does not create a normal Application. Create the system
        // ActivityThread and obtain its Context via reflection.
        Method systemMain = at.getDeclaredMethod("systemMain");
        systemMain.setAccessible(true);
        Object thread = systemMain.invoke(null);

        Method getSystemContext = at.getDeclaredMethod("getSystemContext");
        getSystemContext.setAccessible(true);
        return (Context) getSystemContext.invoke(thread);
    }

    public static void main(String[] args) {
        if (args.length < 2) {
            System.err.println("Usage: IconFetcher <package> <output.png> [size]");
            System.exit(2);
        }

        String packageName = args[0];
        String outputPath = args[1];
        int size = 192;
        if (args.length >= 3) {
            try { size = Math.max(48, Math.min(512, Integer.parseInt(args[2]))); }
            catch (Exception ignored) {}
        }

        try {
            Context context = getSystemContext();
            PackageManager pm = context.getPackageManager();
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

            File out = new File(outputPath);
            File parent = out.getParentFile();
            if (parent != null) parent.mkdirs();

            try (FileOutputStream fos = new FileOutputStream(out)) {
                if (!bitmap.compress(Bitmap.CompressFormat.PNG, 100, fos)) {
                    throw new RuntimeException("PNG compression failed");
                }
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
